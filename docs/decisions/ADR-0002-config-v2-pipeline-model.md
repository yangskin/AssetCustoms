# ADR-0002：配置 v2.0 — 三段式管线模型（Input → Processing → Output）

| 项目 | 值 |
|------|-----|
| 状态 | **已确认（Accepted）** |
| 日期 | 2026-03-23 |
| 决策者 | 项目负责人 |
| 关联 | `requirements_v1.1.md`、`architecture.md`、`schema.py` |

---

## 1. 背景与动机

### 1.1 现状问题

v1.1 的 `PluginConfig` 是扁平结构——所有字段平铺在同一层级。随着功能增长，暴露出三个核心矛盾：

**矛盾 A：贴图独大，Mesh/Material 被弱化**

| 资产类型 | 传入规则 | 处理逻辑 | 交付设置 |
|----------|---------|---------|---------|
| 贴图(Texture) | `texture_input_rules`（30+ 字段） | `texture_output_definitions`（每个 20 字段 × N） | 散落在 output_def 和顶层 |
| 网格(Mesh) | ⚠ 无 | ⚠ 无 | 命名模板 1 字段 + 子目录 1 字段 |
| 材质(Material) | ⚠ 无 | ⚠ 无 | `master_material_path` + 命名模板 + 子目录 |

贴图拥有约 150+ 配置项，Mesh 仅 2 个，Material 仅 3 个。结构未预留其他资产类型的扩展位。

**矛盾 B：`texture_output_definitions` 内部混合三种关注点**

```
TextureOutputDef 当前结构：
├─ 身份信息：enabled, output_name, suffix, category
├─ 🔧 处理逻辑：channels{}, flip_green, normal_space, allow_missing
├─ 📦 输出格式：file_format, bit_depth, srgb, mips, resize, alpha_premultiplied
└─ 🚀 UE 交付：import_settings{}, material_parameter
```

美术看到的是一张大卡片，无法直觉区分"我在配哪个阶段的事"。

**矛盾 C：交付设置高度重复**

当前 4 个 `texture_output_definitions` 包含几乎相同的 `import_settings` 块，仅 `compression` 和 `lod_group` 有差异。`material_parameter` 散落在每个 output_def 里，无法集中查看材质绑定关系。

### 1.2 目标

1. 将配置和 UI 统一到"**传入 → 处理 → 交付**"三段式心智模型。
2. 每个阶段覆盖所有资产类型（贴图、Mesh、材质），而非仅贴图。
3. 消除重复配置（import_settings、material_parameter）。
4. 为未来扩展预留结构位（mesh 处理、LOD、材质参数自动化等）。
5. 美术打开 UI 后，Tab 名即含义——"我给什么 → 怎么处理 → 放哪里"。

---

## 2. 决策：三段式嵌套结构（config_version = "2.0"）

### 2.1 顶层结构

```jsonc
{
  "config_version": "2.0",

  // ===== 阶段一：传入（Input）=====
  "input": { ... },

  // ===== 阶段二：处理（Processing）=====
  "processing": { ... },

  // ===== 阶段三：交付（Output）=====
  "output": { ... }
}
```

### 2.2 各段详细 Schema

#### 2.2.1 `input` — "拿到什么、怎么识别"

```jsonc
"input": {
  // 贴图输入识别规则
  "texture": {
    "match_mode": "glob",           // "glob" | "regex"
    "ignore_case": true,
    "extensions": [".png", ".tga", ".jpg", ".jpeg", ".exr", ".tif", ".tiff"],
    "search_roots": ["{DropDir}", "{DropDir}/Textures", "{DropDir}/Maps", "{DropDir}/*.fbm"],
    "rules": {
      "BaseColor":        { "priority": 10, "patterns": ["*_BC.*", "*_BaseColor.*", ...] },
      "Normal":           { "priority": 10, "patterns": ["*_N.*", "*_Normal.*", ...] },
      "Roughness":        { "priority": 9,  "patterns": ["*_R.*", "*_Rough.*", ...] },
      "Metallic":         { "priority": 9,  "patterns": ["*_M.*", "*_Metal.*", ...] },
      "AmbientOcclusion": { "priority": 8,  "patterns": ["*_AO.*", ...] },
      "Height":           { "priority": 7,  "patterns": ["*_H.*", "*_Height.*", ...] }
    }
  }

  // 🔮 未来扩展预留位：
  // "mesh": {
  //   "accepted_formats": [".fbx", ".obj", ".gltf"],
  //   "import_as": "static_mesh",          // "static_mesh" | "skeletal_mesh"
  //   "auto_generate_collision": false,
  //   "combine_meshes": true
  // },
  // "material": {
  //   "source_mode": "auto"                // "auto" | "manual" | "skip"
  // }
}
```

**从 v1.1 的变化**：
- `texture_input_rules` → `input.texture`（嵌入 input 段）
- 结构内部字段保持不变，仅命名空间迁移

#### 2.2.2 `processing` — "怎么加工"

```jsonc
"processing": {
  // 命名冲突策略（适用于所有资产类型）
  "conflict_policy": "version",      // "overwrite" | "skip" | "version"

  // 贴图处理定义列表（每项定义一张输出贴图的处理规则）
  "texture_definitions": [
    {
      "enabled": true,
      "name": "Diffuse",              // 人类可读名称
      "suffix": "D",                  // 输出文件后缀
      "category": "PBR",              // 分类标签

      // 通道编排（Pillow 处理）
      "channels": {
        "R": { "from": "BaseColor", "ch": "R" },
        "G": { "from": "BaseColor", "ch": "G" },
        "B": { "from": "BaseColor", "ch": "B" },
        "A": { "constant": 1.0 }
      },

      // 处理参数
      "flip_green": false,
      "normal_space": null,           // "OpenGL" | "DirectX" | null
      "allow_missing": false,

      // 输出文件格式
      "format": "PNG",                // "PNG" | "TGA" | "EXR"
      "bit_depth": 8,                 // 8 | 16 | 32
      "srgb": true,
      "mips": true,
      "resize": null,                 // {"width": N, "height": N} | null
      "alpha_premultiplied": false
    }
    // ... 更多定义（Normal, MRO, Height 等）
  ]

  // 🔮 未来扩展预留位：
  // "mesh_processing": {
  //   "auto_lod": false,
  //   "lod_settings": [...],
  //   "simplify_ratio": 1.0,
  //   "remove_degenerate_triangles": true
  // }
}
```

**从 v1.1 的变化**：
- `texture_output_definitions` 拆分为：
  - 处理相关字段 → `processing.texture_definitions`
  - UE 交付相关字段（`import_settings`、`material_parameter`）→ `output` 段
- `conflict_policy` 从顶层移入 `processing`（它控制的是处理行为）
- `file_format` → `format`（简化命名）
- `output_name` → `name`（简化命名）

#### 2.2.3 `output` — "放哪里、叫什么、UE 做什么设置"

```jsonc
"output": {
  // 全局交付路径
  "target_path_template": "",         // 留空 = 使用 Content Browser 当前目录
  "fallback_path": "/Game/AIGC_Dropoff",

  // 子目录布局
  "subdirectories": {
    "static_mesh": "",                // 空 = 放在 target_path 根目录
    "material_instance": "Materials",
    "texture": "Textures"
  },

  // 资产命名
  "naming": {
    "static_mesh": "SM_{Name}",
    "material_instance": "MI_{Name}",
    "texture": "T_{Name}_{Suffix}"
  },

  // 材质交付
  "material": {
    "master_material_path": "/Game/MyProject/Materials/Masters/MM_Prop_PBR.MM_Prop_PBR",
    // 贴图→材质参数绑定（key = texture_definition 的 suffix，value = MI 参数名）
    "parameter_bindings": {
      "D":   "BaseColor_Texture",
      "N":   "Normal_Texture",
      "MRO": "Packed_Texture",
      "H":   "Height_Texture"
    }
  },

  // UE 贴图导入属性 — 默认值
  "texture_import_defaults": {
    "compression": "TC_Default",
    "lod_group": "TEXTUREGROUP_World",
    "srgb": null,                     // null = 沿用 processing 定义的 srgb
    "virtual_texture": false,
    "address_x": "Wrap",
    "address_y": "Wrap",
    "mip_gen": "FromTextureGroup"
  },
  // UE 贴图导入属性 — 按 suffix 覆盖
  "texture_import_overrides": {
    "N":   { "compression": "TC_Normalmap", "lod_group": "TEXTUREGROUP_WorldNormalMap" },
    "MRO": { "compression": "TC_Masks" },
    "H":   { "compression": "TC_Grayscale", "bit_depth": 16 }
  }

  // 🔮 未来扩展预留位：
  // "mesh_delivery": {
  //   "nanite_enabled": false,
  //   "collision_complexity": "UseSimpleAsComplex",
  //   "lod_group": "LargeWorld"
  // }
}
```

**从 v1.1 的变化**：
- `default_master_material_path` → `output.material.master_material_path`
- `default_fallback_import_path` → `output.fallback_path`
- `target_path_template` → `output.target_path_template`
- `asset_naming_template` → `output.naming`
- `asset_subdirectories` → `output.subdirectories`
- `material_parameter`（原分散在每个 TextureOutputDef 里）→ `output.material.parameter_bindings`（集中管理）
- `import_settings`（原每个 TextureOutputDef 都重复）→ `output.texture_import_defaults` + `output.texture_import_overrides`（消除重复）

---

## 3. UI Tab 映射

| 新 Tab | 对应 config 段 | 包含的 UI 控件 | 美术的理解 |
|--------|---------------|---------------|-----------|
| **① 传入 (Input)** | `input` | 匹配模式、扩展名列表、搜索根目录、输入规则表 | "我给工具什么，它怎么认" |
| **② 处理 (Processing)** | `processing` | 冲突策略、贴图处理卡片（通道编排 + 格式 + 处理参数） | "工具怎么加工我的素材" |
| **③ 交付 (Output)** | `output` | 路径/子目录、命名模板、材质路径 + 参数绑定表、UE 导入属性默认值 + 覆盖表 | "处理好的东西放哪、叫什么、UE 怎么设" |

---

## 4. Python Schema 映射（dataclass）

```python
# === input ===
@dataclass
class TextureInputConfig:
    match_mode: str = "glob"
    ignore_case: bool = True
    extensions: list[str] = ...
    search_roots: list[str] = ...
    rules: dict[str, TextureInputRule] = ...

@dataclass
class InputConfig:
    texture: TextureInputConfig = ...
    # 🔮 mesh: MeshInputConfig = ...
    # 🔮 material: MaterialInputConfig = ...

# === processing ===
@dataclass
class TextureProcessingDef:
    enabled: bool = True
    name: str = ""
    suffix: str = ""
    category: str = "PBR"
    channels: dict[str, ChannelDef] = ...
    flip_green: bool = False
    normal_space: str | None = None
    allow_missing: bool = False
    format: str = "PNG"
    bit_depth: int = 8
    srgb: bool = True
    mips: bool = True
    resize: dict[str, int] | None = None
    alpha_premultiplied: bool = False

@dataclass
class ProcessingConfig:
    conflict_policy: str = "version"
    texture_definitions: list[TextureProcessingDef] = ...
    # 🔮 mesh_processing: MeshProcessingConfig = ...

# === output ===
@dataclass
class SubdirectoriesConfig:
    static_mesh: str = ""
    material_instance: str = ""
    texture: str = ""

@dataclass
class NamingConfig:
    static_mesh: str = "SM_{Name}"
    material_instance: str = "MI_{Name}"
    texture: str = "T_{Name}_{Suffix}"

@dataclass
class MaterialOutputConfig:
    master_material_path: str = ""
    parameter_bindings: dict[str, str] = ...  # suffix -> MI param name

@dataclass
class TextureImportDefaults:
    compression: str = "TC_Default"
    lod_group: str = "TEXTUREGROUP_World"
    srgb: bool | None = None
    virtual_texture: bool = False
    address_x: str = "Wrap"
    address_y: str = "Wrap"
    mip_gen: str = "FromTextureGroup"

@dataclass
class OutputConfig:
    target_path_template: str = ""
    fallback_path: str = "/Game/AIGC_Dropoff"
    subdirectories: SubdirectoriesConfig = ...
    naming: NamingConfig = ...
    material: MaterialOutputConfig = ...
    texture_import_defaults: TextureImportDefaults = ...
    texture_import_overrides: dict[str, dict] = ...  # suffix -> partial overrides
    # 🔮 mesh_delivery: MeshDeliveryConfig = ...

# === 顶层 ===
@dataclass
class PluginConfig:
    config_version: str = "2.0"
    input: InputConfig = ...
    processing: ProcessingConfig = ...
    output: OutputConfig = ...
```

---

## 5. 完整 JSONC 示例（Prop.jsonc v2.0）

```jsonc
{
  "config_version": "2.0",

  // =====================================================================
  // 阶段一：传入（Input）— "拿到什么、怎么识别"
  // =====================================================================
  "input": {
    "texture": {
      "match_mode": "glob",
      "ignore_case": true,
      "extensions": [".png", ".tga", ".jpg", ".jpeg", ".exr", ".tif", ".tiff"],
      "search_roots": [
        "{DropDir}",
        "{DropDir}/Textures",
        "{DropDir}/Maps",
        "{DropDir}/*.fbm"
      ],
      "rules": {
        "BaseColor":        { "priority": 10, "patterns": ["*_BC.*", "*_BC_*", "*_BaseColor.*", "*_BaseColor_*", "*_Diffuse.*", "*_Diffuse_*", "*_Albedo.*", "*_Albedo_*", "*_rgb_*", "*_rgb.*", "*_color_*", "*_color.*"] },
        "Normal":           { "priority": 10, "patterns": ["*_N.*", "*_N_*", "*_Normal.*", "*_Normal_*", "*_Nrm.*", "*_Nrm_*"] },
        "Roughness":        { "priority": 9,  "patterns": ["*_R.*", "*_R_*", "*_Rough.*", "*_Rough_*", "*_Roughness.*", "*_Roughness_*"] },
        "Metallic":         { "priority": 9,  "patterns": ["*_M.*", "*_M_*", "*_Metal.*", "*_Metal_*", "*_Metallic.*", "*_Metallic_*"] },
        "AmbientOcclusion": { "priority": 8,  "patterns": ["*_AO.*", "*_AO_*", "*_AmbientOcclusion.*", "*_AmbientOcclusion_*"] },
        "Height":           { "priority": 7,  "patterns": ["*_H.*", "*_H_*", "*_Height.*", "*_Height_*", "*_Displacement.*", "*_Displacement_*"] }
      }
    }
  },

  // =====================================================================
  // 阶段二：处理（Processing）— "怎么加工"
  // =====================================================================
  "processing": {
    "conflict_policy": "version",

    "texture_definitions": [
      {
        "enabled": true,
        "name": "Diffuse",
        "suffix": "D",
        "category": "PBR",
        "channels": {
          "R": { "from": "BaseColor", "ch": "R" },
          "G": { "from": "BaseColor", "ch": "G" },
          "B": { "from": "BaseColor", "ch": "B" },
          "A": { "constant": 1.0 }
        },
        "flip_green": false,
        "normal_space": null,
        "allow_missing": false,
        "format": "PNG",
        "bit_depth": 8,
        "srgb": true,
        "mips": true,
        "resize": null,
        "alpha_premultiplied": false
      },
      {
        "enabled": true,
        "name": "Normal",
        "suffix": "N",
        "category": "PBR",
        "channels": {
          "R": { "from": "Normal", "ch": "R", "constant": 0.5 },
          "G": { "from": "Normal", "ch": "G", "constant": 0.5 },
          "B": { "from": "Normal", "ch": "B", "constant": 1.0 },
          "A": { "constant": 1.0 }
        },
        "flip_green": true,
        "normal_space": "OpenGL",
        "allow_missing": true,
        "format": "PNG",
        "bit_depth": 8,
        "srgb": false,
        "mips": true
      },
      {
        "enabled": true,
        "name": "Packed_MRO",
        "suffix": "MRO",
        "category": "PBR",
        "channels": {
          "R": { "from": "Metallic",         "ch": "R", "constant": 0.0 },
          "G": { "from": "Roughness",        "ch": "R", "constant": 0.5 },
          "B": { "from": "AmbientOcclusion", "ch": "R", "constant": 1.0 },
          "A": { "constant": 1.0 }
        },
        "allow_missing": true,
        "format": "PNG",
        "bit_depth": 8,
        "srgb": false,
        "mips": true
      },
      {
        "enabled": true,
        "name": "Height",
        "suffix": "H",
        "category": "PBR",
        "channels": {
          "R": { "from": "Height", "ch": "R", "remap": [0.0, 1.0, 0.0, 1.0], "constant": 0.0 },
          "G": { "from": "Height", "ch": "R", "constant": 0.0 },
          "B": { "from": "Height", "ch": "R", "constant": 0.0 },
          "A": { "constant": 1.0 }
        },
        "allow_missing": true,
        "format": "PNG",
        "bit_depth": 16,
        "srgb": false,
        "mips": true
      }
    ]
  },

  // =====================================================================
  // 阶段三：交付（Output）— "放哪里、叫什么、UE 怎么设"
  // =====================================================================
  "output": {
    "target_path_template": "",
    "fallback_path": "/Game/AIGC_Dropoff",

    "subdirectories": {
      "static_mesh": "",
      "material_instance": "Materials",
      "texture": "Textures"
    },

    "naming": {
      "static_mesh": "SM_{Name}",
      "material_instance": "MI_{Name}",
      "texture": "T_{Name}_{Suffix}"
    },

    "material": {
      "master_material_path": "/Game/MyProject/Materials/Masters/MM_Prop_PBR.MM_Prop_PBR",
      "parameter_bindings": {
        "D":   "BaseColor_Texture",
        "N":   "Normal_Texture",
        "MRO": "Packed_Texture",
        "H":   "Height_Texture"
      }
    },

    "texture_import_defaults": {
      "compression": "TC_Default",
      "lod_group": "TEXTUREGROUP_World",
      "virtual_texture": false,
      "address_x": "Wrap",
      "address_y": "Wrap",
      "mip_gen": "FromTextureGroup"
    },

    "texture_import_overrides": {
      "N":   { "compression": "TC_Normalmap", "lod_group": "TEXTUREGROUP_WorldNormalMap" },
      "MRO": { "compression": "TC_Masks" },
      "H":   { "compression": "TC_Grayscale" }
    }
  }
}
```

---

## 6. 字段迁移映射表（v1.1 → v2.0）

| v1.1 字段 | v2.0 位置 | 备注 |
|-----------|----------|------|
| `config_version` | `config_version` | 值变为 `"2.0"` |
| `default_master_material_path` | `output.material.master_material_path` | — |
| `default_fallback_import_path` | `output.fallback_path` | 简化命名 |
| `target_path_template` | `output.target_path_template` | — |
| `conflict_policy` | `processing.conflict_policy` | 移入 processing |
| `asset_naming_template.static_mesh` | `output.naming.static_mesh` | — |
| `asset_naming_template.material_instance` | `output.naming.material_instance` | — |
| `asset_naming_template.texture` | `output.naming.texture` | — |
| `asset_subdirectories.static_mesh` | `output.subdirectories.static_mesh` | — |
| `asset_subdirectories.material_instance` | `output.subdirectories.material_instance` | — |
| `asset_subdirectories.texture` | `output.subdirectories.texture` | — |
| `texture_input_rules.*` | `input.texture.*` | 内部结构不变 |
| `texture_output_definitions[].output_name` | `processing.texture_definitions[].name` | 简化命名 |
| `texture_output_definitions[].suffix` | `processing.texture_definitions[].suffix` | — |
| `texture_output_definitions[].category` | `processing.texture_definitions[].category` | — |
| `texture_output_definitions[].enabled` | `processing.texture_definitions[].enabled` | — |
| `texture_output_definitions[].channels` | `processing.texture_definitions[].channels` | — |
| `texture_output_definitions[].flip_green` | `processing.texture_definitions[].flip_green` | — |
| `texture_output_definitions[].normal_space` | `processing.texture_definitions[].normal_space` | — |
| `texture_output_definitions[].allow_missing` | `processing.texture_definitions[].allow_missing` | — |
| `texture_output_definitions[].file_format` | `processing.texture_definitions[].format` | 简化命名 |
| `texture_output_definitions[].bit_depth` | `processing.texture_definitions[].bit_depth` | — |
| `texture_output_definitions[].srgb` | `processing.texture_definitions[].srgb` | — |
| `texture_output_definitions[].mips` | `processing.texture_definitions[].mips` | — |
| `texture_output_definitions[].resize` | `processing.texture_definitions[].resize` | — |
| `texture_output_definitions[].alpha_premultiplied` | `processing.texture_definitions[].alpha_premultiplied` | — |
| `texture_output_definitions[].material_parameter` | `output.material.parameter_bindings[suffix]` | **集中管理** |
| `texture_output_definitions[].import_settings.*` | `output.texture_import_defaults` + `output.texture_import_overrides[suffix]` | **消除重复** |
| `texture_merge` / `allowed_modes` | 🗑 **删除** | 旧版兼容字段，v2.0 不再保留 |

---

## 7. 向后兼容策略

**不兼容。** 直接采用 v2.0 结构，不保留 v1.1 迁移逻辑。现有 JSONC 文件将被重写。

---

## 8. 受影响文件

| 文件 | 变更程度 | 说明 |
|------|---------|------|
| `core/config/schema.py` | **大** | 重写 dataclass 结构 |
| `core/config/loader.py` | **大** | 重写解析逻辑 |
| `config_editor.py` | **大** | Tab 重构为 Input / Processing / Output |
| `Prop.jsonc` | **大** | 重写为 v2.0 结构 |
| `Character.jsonc` | **大** | 重写为 v2.0 结构 |
| `core/naming.py` | **中** | 字段访问路径变更 |
| `import_pipeline.py` | **中** | 字段访问路径变更 |
| `import_context.py` | **小** | 无结构变化 |
| `actions.py` | **小** | 字段访问路径变更 |
| 测试文件（5+） | **中** | 适配新结构 |
| `docs/*` | **中** | 需求文档 + 架构文档更新 |

---

## 9. 实施计划

| 阶段 | 内容 | 验证方式 |
|------|------|---------|
| **Step 1** | Schema（dataclass）+ Loader 重写 | 单元测试全 pass |
| **Step 2** | Prop.jsonc + Character.jsonc 重写 | load_config 加载 + 字段断言 |
| **Step 3** | naming.py + import_pipeline.py + actions.py 适配 | 现有功能测试 |
| **Step 4** | config_editor.py UI 重构（3 Tab） | 视觉验证 + 保存/加载往返测试 |
| **Step 5** | 测试全量更新 + 文档同步 | 全量测试 pass |

---

## 10. 决策记录（已确认 2026-03-23）

> 以下问题已由决策者确认。

### Q1：`format` / `bit_depth` / `srgb` / `mips` 归属

**决策：保留在 `processing.texture_definitions`。**

理由：这些字段直接控制 Pillow 保存行为（`Image.save()` 的参数），属于处理阶段。UE 端的 srgb 另由 `output.texture_import_defaults.srgb` 控制。

### Q2：`conflict_policy` 归属

**决策：保留在 `processing`。**

补充确认：冲突策略在处理阶段就需要决策——必须先确定导入模型的最终命名，后续所有资产（SM/MI/Texture）的命名都基于此。命名冲突决策是处理链的前置步骤。

### Q3：`parameter_bindings` 的 key

**决策：使用 `suffix`（"D", "N", "MRO"）。**

理由：简短唯一，与 `{Suffix}` 占位符一致，是天然的索引键。

### Q4：旧版字段（`texture_merge` / `allowed_modes`）

**决策：直接删除，不保留兼容。** 同步修改所有引用这些字段的代码和模板（schema.py、loader.py、测试文件等）。

### Q5：`input.mesh` 和 `input.material`

**决策：暂时留空（仅注释占位）。**

补充说明：导入资产主要是 Mesh + Texture。材质通常嵌在模型文件中（部分格式有独立材质配置文件，但当前非主要场景）。后续有需求时按三段式结构扩展即可。

### Q6：`texture_import_overrides` UI 呈现

**决策：方案 A — Output Tab 内集中表格。**

行 = suffix，列 = compression / lod_group / srgb / ...，仅显示有覆盖的行。符合"交付设置统一管理"原则。
