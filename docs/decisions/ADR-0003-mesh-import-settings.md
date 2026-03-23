# ADR-0003: 模型导入设置（Mesh Import Settings）

- **状态**: 评估中（Draft）
- **日期**: 2026-03-23
- **关联**: ADR-0002 Config v2.0 三段式管线模型

---

## 1. 背景与动机

当前 `import_pipeline.py` 中 FBX 导入仅使用 4 项硬编码设置：

```python
fbx_options.set_editor_property("import_mesh", True)
fbx_options.set_editor_property("import_textures", import_textures)
fbx_options.set_editor_property("import_materials", True)
fbx_options.set_editor_property("import_as_skeletal", False)
```

对于不同 Profile（Prop / Character）的模型，缩放、法线/切线导入方式、顶点色、动画等常用设置无法通过配置文件控制。美术需要在每次导入后手动调整这些属性，效率低且容易遗漏。

**目标**：在 Config v2.0 框架下新增 **模型导入配置段**，让这些设置可通过 JSONC 配置和 UI 编辑器控制。

---

## 2. UE5 Python API 可行性分析

### 2.1 API 继承链

```
unreal.Object
  └─ unreal.FbxImportUI                    ← 顶层导入选项
       ├─ .static_mesh_import_data         → FbxStaticMeshImportData
       ├─ .skeletal_mesh_import_data       → FbxSkeletalMeshImportData
       ├─ .anim_sequence_import_data       → FbxAnimSequenceImportData
       └─ .texture_import_data             → FbxTextureImportData

unreal.FbxStaticMeshImportData (FbxMeshImportData → FbxAssetImportData)
  继承属性：
    import_uniform_scale      : float       ← 统一缩放
    import_rotation           : Rotator     ← 导入旋转偏移
    import_translation        : Vector      ← 导入位移偏移
    convert_scene             : bool        ← 转换场景坐标系
    convert_scene_unit        : bool        ← 转换场景单位
    force_front_x_axis        : bool        ← 强制 X 轴朝前
    normal_import_method      : FBXNormalImportMethod
    normal_generation_method  : FBXNormalGenerationMethod
    compute_weighted_normals  : bool
    reorder_material_to_fbx_order : bool
    transform_vertex_to_absolute  : bool
    bake_pivot_in_vertex      : bool
    import_mesh_lods          : bool
  自有属性：
    auto_generate_collision   : bool
    build_nanite              : bool
    build_reversed_index_buffer : bool
    combine_meshes            : bool
    generate_lightmap_u_vs    : bool
    remove_degenerates        : bool
    one_convex_hull_per_ucx   : bool
    static_mesh_lod_group     : Name
    distance_field_resolution_scale : float
    vertex_color_import_option : VertexColorImportOption
    vertex_override_color     : Color
```

### 2.2 FbxImportUI 顶层属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `import_mesh` | bool | 是否导入网格 |
| `import_animations` | bool | 是否导入动画 |
| `import_materials` | bool | 是否导入材质 |
| `import_textures` | bool | 是否导入贴图 |
| `import_as_skeletal` | bool | 作为骨骼网格导入 |
| `import_rigid_mesh` | bool | 刚体网格 |
| `mesh_type_to_import` | FBXImportType | STATIC_MESH / SKELETAL_MESH / ANIMATION |
| `create_physics_asset` | bool | 创建物理资产 |
| `override_full_name` | bool | 覆盖资产全名 |
| `lod_number` | int | LOD 数量 |

### 2.3 关键枚举

```python
# 法线/切线导入模式
unreal.FBXNormalImportMethod:
    FBXNIM_COMPUTE_NORMALS              # 重新计算法线
    FBXNIM_IMPORT_NORMALS               # 导入法线（重算切线）
    FBXNIM_IMPORT_NORMALS_AND_TANGENTS  # 导入法线和切线

# 法线生成算法
unreal.FBXNormalGenerationMethod:
    BUILT_IN                            # 引擎内置
    MIKK_T_SPACE                        # MikkTSpace

# 顶点色导入选项
unreal.VertexColorImportOption:
    REPLACE                             # 替换现有
    IGNORE                              # 忽略
    OVERRIDE                            # 覆盖为指定颜色

# FBX 导入类型
unreal.FBXImportType:
    FBXIT_STATIC_MESH                   # 静态网格
    FBXIT_SKELETAL_MESH                 # 骨骼网格
    FBXIT_ANIMATION                     # 动画

# 坐标系策略（editor property）
unreal.CoordinateSystemPolicy:
    KEEP_XYZ_AXES
    MATCH_UP_AXIS
    MATCH_UP_FORWARD_AXES
```

### 2.4 Python 设置方式验证

```python
task = unreal.AssetImportTask()
task.set_editor_property("filename", fbx_path)
task.set_editor_property("destination_path", dest)
task.set_editor_property("automated", True)
task.set_editor_property("replace_existing", True)

fbx_ui = unreal.FbxImportUI()
fbx_ui.set_editor_property("import_mesh", True)
fbx_ui.set_editor_property("import_animations", False)
fbx_ui.set_editor_property("import_as_skeletal", False)

# 获取 static_mesh_import_data 子对象并设置属性
sm_data = fbx_ui.get_editor_property("static_mesh_import_data")
sm_data.set_editor_property("import_uniform_scale", 1.0)
sm_data.set_editor_property("normal_import_method",
    unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS)
sm_data.set_editor_property("normal_generation_method",
    unreal.FBXNormalGenerationMethod.MIKK_T_SPACE)
sm_data.set_editor_property("vertex_color_import_option",
    unreal.VertexColorImportOption.REPLACE)
sm_data.set_editor_property("auto_generate_collision", True)
sm_data.set_editor_property("build_nanite", False)
sm_data.set_editor_property("combine_meshes", True)

task.set_editor_property("options", fbx_ui)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
```

**结论：所有属性均可通过 Python API 设置，无需 C++ 扩展。** ✅

---

## 3. 配置方案设计

### 3.1 在 v2.0 三段式中的位置

模型导入设置属于 **"怎么加工"**（Processing） 阶段和 **"UE 怎么设"**（Output） 阶段的交集。

考虑到与现有 `texture_import_defaults / texture_import_overrides` 模式保持一致，建议：

- **Processing 层** 新增 `mesh_import` 字段：控制 FBX 导入行为（缩放、动画、切线等）
- 属于"导入时应用的参数"而非"导入后 UE 资产属性"

> 注：也可以放在 Output 层。但考虑到 `import_uniform_scale`、`normal_import_method` 等是在
> **导入过程中** 就必须设定的（通过 FbxImportUI 传入），不是导入后修改的属性，
> 放在 Processing 更契合"加工方式"的语义。

### 3.2 Schema 新增数据结构

```python
@dataclass
class MeshImportConfig:
    """FBX 模型导入设置。"""

    # ── 基础 ──
    import_uniform_scale: float = 1.0            # 统一缩放系数
    import_as_skeletal: bool = False              # 作为骨骼网格导入

    # ── 法线与切线 ──
    normal_import_method: str = "ImportNormalsAndTangents"
        # "ComputeNormals" | "ImportNormals" | "ImportNormalsAndTangents"
    normal_generation_method: str = "MikkTSpace"
        # "BuiltIn" | "MikkTSpace"
    compute_weighted_normals: bool = True

    # ── 顶点色 ──
    vertex_color_import_option: str = "Replace"
        # "Replace" | "Ignore" | "Override"
    vertex_override_color: Optional[List[int]] = None  # [R, G, B, A] 0-255，仅 Override 模式

    # ── 动画 ──
    import_animations: bool = False              # 是否导入动画数据

    # ── 碰撞与几何 ──
    auto_generate_collision: bool = True
    combine_meshes: bool = True
    remove_degenerates: bool = True
    build_nanite: bool = False
    build_reversed_index_buffer: bool = True
    generate_lightmap_u_vs: bool = True

    # ── 坐标变换 ──
    convert_scene: bool = True
    convert_scene_unit: bool = True
    force_front_x_axis: bool = False
    import_rotation: Optional[List[float]] = None     # [Pitch, Yaw, Roll]
    import_translation: Optional[List[float]] = None  # [X, Y, Z]

    # ── LOD ──
    import_mesh_lods: bool = False
    static_mesh_lod_group: str = "None"          # Name 类型，LOD 组名

    # ── 材质 ──
    import_materials: bool = True
    import_textures: bool = True                 # 是否让 FBX Factory 导入贴图
    reorder_material_to_fbx_order: bool = True
```

### 3.3 JSONC 配置示例

```jsonc
{
  "config_version": "2.0",

  // === 阶段二：处理（Processing） ===
  "processing": {
    "conflict_policy": "version",

    // 模型导入设置
    "mesh_import": {
      "import_uniform_scale": 1.0,
      "import_as_skeletal": false,

      "normal_import_method": "ImportNormalsAndTangents",
      "normal_generation_method": "MikkTSpace",
      "compute_weighted_normals": true,

      "vertex_color_import_option": "Replace",

      "import_animations": false,

      "auto_generate_collision": true,
      "combine_meshes": true,
      "remove_degenerates": true,
      "build_nanite": false,
      "generate_lightmap_u_vs": true,

      "convert_scene": true,
      "convert_scene_unit": true,

      "import_mesh_lods": false,

      "import_materials": true,
      "import_textures": true
    },

    "texture_definitions": [ ... ]
  }
}
```

### 3.4 与现有代码的对接方式

`import_pipeline.py` 的 `import_fbx()` 方法改造：

```python
def import_fbx(self, fbx_path, destination_path, config: PluginConfig) -> List[str]:
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", fbx_path)
    task.set_editor_property("destination_path", destination_path)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    task.set_editor_property("replace_existing", True)

    mc = config.processing.mesh_import  # MeshImportConfig

    fbx_ui = unreal.FbxImportUI()
    fbx_ui.set_editor_property("import_mesh", True)
    fbx_ui.set_editor_property("import_animations", mc.import_animations)
    fbx_ui.set_editor_property("import_materials", mc.import_materials)
    fbx_ui.set_editor_property("import_textures", mc.import_textures)
    fbx_ui.set_editor_property("import_as_skeletal", mc.import_as_skeletal)

    # 静态网格自定义
    sm = fbx_ui.get_editor_property("static_mesh_import_data")
    sm.set_editor_property("import_uniform_scale", mc.import_uniform_scale)
    sm.set_editor_property("normal_import_method", _map_normal_import(mc.normal_import_method))
    sm.set_editor_property("normal_generation_method", _map_normal_gen(mc.normal_generation_method))
    sm.set_editor_property("compute_weighted_normals", mc.compute_weighted_normals)
    sm.set_editor_property("vertex_color_import_option", _map_vertex_color(mc.vertex_color_import_option))
    sm.set_editor_property("auto_generate_collision", mc.auto_generate_collision)
    sm.set_editor_property("combine_meshes", mc.combine_meshes)
    sm.set_editor_property("remove_degenerates", mc.remove_degenerates)
    sm.set_editor_property("build_nanite", mc.build_nanite)
    sm.set_editor_property("build_reversed_index_buffer", mc.build_reversed_index_buffer)
    sm.set_editor_property("generate_lightmap_u_vs", mc.generate_lightmap_u_vs)
    sm.set_editor_property("convert_scene", mc.convert_scene)
    sm.set_editor_property("convert_scene_unit", mc.convert_scene_unit)
    sm.set_editor_property("force_front_x_axis", mc.force_front_x_axis)
    sm.set_editor_property("import_mesh_lods", mc.import_mesh_lods)
    sm.set_editor_property("reorder_material_to_fbx_order", mc.reorder_material_to_fbx_order)
    if mc.import_rotation:
        sm.set_editor_property("import_rotation", unreal.Rotator(*mc.import_rotation))
    if mc.import_translation:
        sm.set_editor_property("import_translation", unreal.Vector(*mc.import_translation))

    task.set_editor_property("options", fbx_ui)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    imported = task.get_editor_property("imported_object_paths")
    return list(imported) if imported else []
```

枚举映射辅助函数：

```python
_NORMAL_IMPORT_MAP = {
    "ComputeNormals":              unreal.FBXNormalImportMethod.FBXNIM_COMPUTE_NORMALS,
    "ImportNormals":               unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS,
    "ImportNormalsAndTangents":    unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS,
}

_NORMAL_GEN_MAP = {
    "BuiltIn":    unreal.FBXNormalGenerationMethod.BUILT_IN,
    "MikkTSpace": unreal.FBXNormalGenerationMethod.MIKK_T_SPACE,
}

_VERTEX_COLOR_MAP = {
    "Replace":  unreal.VertexColorImportOption.REPLACE,
    "Ignore":   unreal.VertexColorImportOption.IGNORE,
    "Override": unreal.VertexColorImportOption.OVERRIDE,
}
```

---

## 4. UI 编辑器扩展

在现有 `config_editor.py` 的 `ConfigEditorWindow` 中新增 **Mesh Import** 面板卡片。

### 4.1 UI 控件映射

| 配置项 | 控件类型 | 默认值 |
|--------|----------|--------|
| `import_uniform_scale` | LabeledFloat (QDoubleSpinBox) | 1.0 |
| `import_as_skeletal` | LabeledCheck (QCheckBox) | False |
| `normal_import_method` | LabeledCombo (QComboBox) | ImportNormalsAndTangents |
| `normal_generation_method` | LabeledCombo | MikkTSpace |
| `compute_weighted_normals` | LabeledCheck | True |
| `vertex_color_import_option` | LabeledCombo | Replace |
| `import_animations` | LabeledCheck | False |
| `auto_generate_collision` | LabeledCheck | True |
| `combine_meshes` | LabeledCheck | True |
| `remove_degenerates` | LabeledCheck | True |
| `build_nanite` | LabeledCheck | False |
| `build_reversed_index_buffer` | LabeledCheck | True |
| `generate_lightmap_u_vs` | LabeledCheck | True |
| `convert_scene` | LabeledCheck | True |
| `convert_scene_unit` | LabeledCheck | True |
| `force_front_x_axis` | LabeledCheck | False |
| `import_mesh_lods` | LabeledCheck | False |
| `static_mesh_lod_group` | LabeledLine (QLineEdit) | "None" |
| `import_materials` | LabeledCheck | True |
| `import_textures` | LabeledCheck | True |
| `reorder_material_to_fbx_order` | LabeledCheck | True |

### 4.2 UI 布局建议

在 Processing 标签页中，`texture_definitions` 列表上方或下方，插入一个 **"Mesh Import"** 可折叠分组框（QGroupBox），内部再分为：

```
┌─ Mesh Import Settings ──────────────────────────┐
│                                                    │
│  ── 基础 ──                                       │
│  Scale: [1.0    ]  □ Import as Skeletal           │
│                                                    │
│  ── 法线与切线 ──                                  │
│  Normal Import: [ImportNormalsAndTangents ▼]      │
│  Normal Gen:    [MikkTSpace ▼]                    │
│  □ Compute Weighted Normals                       │
│                                                    │
│  ── 顶点色 ──                                     │
│  Vertex Color:  [Replace ▼]                       │
│                                                    │
│  ── 动画 ──                                       │
│  □ Import Animations                               │
│                                                    │
│  ── 几何与碰撞 ──                                  │
│  □ Auto Generate Collision  □ Combine Meshes      │
│  □ Remove Degenerates       □ Build Nanite        │
│  □ Build Reversed Index     □ Generate Lightmap UVs│
│                                                    │
│  ── 坐标 ──                                       │
│  □ Convert Scene            □ Convert Scene Unit  │
│  □ Force Front X Axis                              │
│                                                    │
│  ── LOD ──                                        │
│  □ Import Mesh LODs                                │
│  LOD Group: [None          ]                       │
│                                                    │
│  ── 材质/贴图导入 ──                               │
│  □ Import Materials         □ Import Textures     │
│  □ Reorder Material to FBX Order                  │
│                                                    │
└────────────────────────────────────────────────────┘
```

---

## 5. 改动范围评估

### 5.1 需要修改的文件

| 文件 | 改动内容 | 复杂度 |
|------|----------|--------|
| `core/config/schema.py` | 新增 `MeshImportConfig` dataclass；`ProcessingConfig` 加 `mesh_import` 字段 | 低 |
| `core/config/loader.py` | `_parse_processing()` 新增 `mesh_import` 解析逻辑 | 低 |
| `unreal_integration/import_pipeline.py` | `import_fbx()` 读取 `config.processing.mesh_import` 设置 FBX 参数 | 中 |
| `unreal_integration/config_editor.py` | 新增 Mesh Import 面板 UI | 中 |
| `Content/Config/AssetCustoms/Prop.jsonc` | 添加 `processing.mesh_import` 段 | 低 |
| `Content/Config/AssetCustoms/Character.jsonc` | 添加 `processing.mesh_import` 段 | 低 |

### 5.2 不需要修改的文件

| 文件 | 原因 |
|------|------|
| `core/pipeline/check_chain.py` | 检查链不涉及网格导入参数 |
| `core/pipeline/standardize.py` | 贴图标准化流程不受影响 |
| `core/pipeline/triage_ui.py` | 错误分诊 UI 不涉及网格配置 |
| `core/textures/` | 贴图匹配/通道编排与网格无关 |

### 5.3 测试影响

| 测试文件 | 需要更新 |
|----------|----------|
| `test_config_schema*.py` | 需新增 `MeshImportConfig` 测试 |
| `test_config_loader.py` | 需新增带 `mesh_import` 的 JSONC 解析测试 |
| 新增 `test_mesh_import_config.py` | 专门测试枚举映射、默认值等 |

---

## 6. 各 Profile 推荐默认值

### 6.1 Prop 配置

```jsonc
"mesh_import": {
    "import_uniform_scale": 1.0,
    "import_as_skeletal": false,
    "normal_import_method": "ImportNormalsAndTangents",
    "normal_generation_method": "MikkTSpace",
    "compute_weighted_normals": true,
    "vertex_color_import_option": "Ignore",
    "import_animations": false,
    "auto_generate_collision": true,
    "combine_meshes": true,
    "remove_degenerates": true,
    "build_nanite": false,
    "generate_lightmap_u_vs": true,
    "convert_scene": true,
    "convert_scene_unit": true,
    "import_mesh_lods": false,
    "import_materials": true,
    "import_textures": true,
    "reorder_material_to_fbx_order": true
}
```

### 6.2 Character 配置

```jsonc
"mesh_import": {
    "import_uniform_scale": 1.0,
    "import_as_skeletal": false,
    "normal_import_method": "ImportNormalsAndTangents",
    "normal_generation_method": "MikkTSpace",
    "compute_weighted_normals": true,
    "vertex_color_import_option": "Ignore",
    "import_animations": false,
    "auto_generate_collision": false,
    "combine_meshes": true,
    "remove_degenerates": true,
    "build_nanite": false,
    "generate_lightmap_u_vs": false,
    "convert_scene": true,
    "convert_scene_unit": true,
    "import_mesh_lods": false,
    "import_materials": true,
    "import_textures": true,
    "reorder_material_to_fbx_order": true
}
```

**与 Prop 的区别**：
- `auto_generate_collision`: false（角色通常使用 Capsule 碰撞体而非自动凸包）
- `generate_lightmap_u_vs`: false（角色不需要 Lightmap UV）

---

## 7. 向后兼容策略

- **缺省时全部使用默认值**：如果 JSONC 中没有 `mesh_import` 段，`MeshImportConfig()` 使用全默认值。
- 现有 `Prop.jsonc` 和 `Character.jsonc` **不会被破坏**：loader 解析时 `mesh_import` 拿不到就用默认实例。
- `import_fbx()` 的函数签名改为接收 `config: PluginConfig`（或 `mesh_import: MeshImportConfig`），但保持对外行为一致。

---

## 8. 风险与注意事项

| 风险 | 缓解措施 |
|------|----------|
| `import_as_skeletal = True` 时 `static_mesh_import_data` 不适用 | 在代码中判断：为 `True` 时改用 `skeletal_mesh_import_data` |
| 枚举字符串拼写错误导致运行时崩溃 | 枚举映射函数加 `.get()` 兜底 + 日志警告 |
| `import_rotation / import_translation` 为 `None` 时不能传入 UE | 条件判断 `if mc.import_rotation:` 再设置 |
| `vertex_override_color` 只在 `Override` 模式有意义 | 仅当 `vertex_color_import_option == "Override"` 时传入 |
| 大量 bool 属性容易遗漏某项 | UI 编辑器分组显示 + JSONC 注释辅助 |

---

## 9. 实施计划（建议步骤）

| 步骤 | 内容 | 预估文件 |
|------|------|----------|
| Step 1 | `schema.py` 新增 `MeshImportConfig`；`ProcessingConfig.mesh_import` 字段 | 1 文件 |
| Step 2 | `loader.py` 新增 `_parse_mesh_import()` + 集成到 `_parse_processing()` | 1 文件 |
| Step 3 | `import_pipeline.py` 改造 `import_fbx()` 读取配置 | 1 文件 |
| Step 4 | 更新 `Prop.jsonc` + `Character.jsonc` | 2 文件 |
| Step 5 | `config_editor.py` 新增 Mesh Import 面板 | 1 文件 |
| Step 6 | 新增/更新测试 | 2-3 文件 |

---

## 10. 结论

**可行性：完全可行** ✅

- UE5.7 Python API 完整暴露了 `FbxImportUI`、`FbxStaticMeshImportData`（及骨骼、动画）的所有导入属性。
- 所有属性均可通过 `set_editor_property()` 设置，无需 C++ 扩展。
- 配置方案与现有 Config v2.0 三段式架构无缝融合：在 `processing` 段新增 `mesh_import` 对象。
- UI 编辑器可复用现有 `LabeledCheck` / `LabeledCombo` / `LabeledFloat` 控件，增量开发。
- 向后兼容无问题：缺省使用全默认值。

---

## 附录 A: SkeletalMesh 导入支持评估（2026-03-23 追加）

### A.1 需求

当配置中 `import_as_skeletal = true` 时：
1. 应切换到 `FbxSkeletalMeshImportData` 设置属性（而非 `FbxStaticMeshImportData`）
2. 增加 **选择已有 Skeleton 资产路径** 的配置项
3. 暴露 Skeletal 专有的导入选项
4. UI 中根据 `import_as_skeletal` 开关动态切换 StaticMesh / SkeletalMesh 专有控件可见性

### A.2 API 继承结构与属性分类

```
FbxMeshImportData (基类 — Static 与 Skeletal 共享)
├── FbxStaticMeshImportData   ← 静态网格专有属性
└── FbxSkeletalMeshImportData ← 骨骼网格专有属性

FbxImportUI (顶层)
├── skeleton: Skeleton                     ← 已有骨骼资产引用（核心需求）
├── create_physics_asset: bool             ← 创建物理资产
├── physics_asset: PhysicsAsset            ← 已有物理资产引用
├── import_as_skeletal: bool
├── import_rigid_mesh: bool
├── static_mesh_import_data                → FbxStaticMeshImportData
├── skeletal_mesh_import_data              → FbxSkeletalMeshImportData
└── anim_sequence_import_data              → FbxAnimSequenceImportData
```

### A.3 属性三分表（共享 / StaticMesh 专有 / SkeletalMesh 专有）

#### 共享属性（FbxMeshImportData 基类）

| 属性 | 类型 | 说明 | 已在 MeshImportConfig |
|------|------|------|:-----:|
| `import_uniform_scale` | float | 统一缩放 | ✅ |
| `normal_import_method` | FBXNormalImportMethod | 法线导入方式 | ✅ |
| `normal_generation_method` | FBXNormalGenerationMethod | 法线生成方式 | ✅ |
| `compute_weighted_normals` | bool | 加权法线 | ✅ |
| `reorder_material_to_fbx_order` | bool | 按 FBX 顺序排列材质 | ✅ |
| `import_mesh_lods` | bool | 导入 LOD 网格 | ✅ |
| `convert_scene` | bool | 转换场景坐标系 | ✅ |
| `convert_scene_unit` | bool | 转换场景单位 | ✅ |
| `force_front_x_axis` | bool | 强制 X 轴朝前 | ✅ |
| `import_rotation` | Rotator | 导入旋转偏移 | ✅ |
| `import_translation` | Vector | 导入位移偏移 | ✅ |
| `bake_pivot_in_vertex` | bool | 烘焙枢轴到顶点 | ❌ |
| `transform_vertex_to_absolute` | bool | 顶点变换为绝对坐标 | ❌ |
| `vertex_color_import_option` | VertexColorImportOption | 顶点色导入 | ✅ |
| `vertex_override_color` | Color | 顶点色覆盖颜色 | ✅ |

#### StaticMesh 专有属性（FbxStaticMeshImportData）

| 属性 | 类型 | 说明 | 已在 MeshImportConfig | Skeletal 时行为 |
|------|------|------|:-----:|---------|
| `auto_generate_collision` | bool | 自动生成碰撞 | ✅ | **禁用/隐藏** |
| `build_nanite` | bool | 构建 Nanite | ✅ | **禁用/隐藏** |
| `build_reversed_index_buffer` | bool | 反向索引缓冲 | ✅ | **禁用/隐藏** |
| `combine_meshes` | bool | 合并网格 | ✅ | **禁用/隐藏** |
| `generate_lightmap_u_vs` | bool | 生成光照贴图 UV | ✅ | **禁用/隐藏** |
| `remove_degenerates` | bool | 移除退化三角形 | ✅ | **禁用/隐藏** |
| `static_mesh_lod_group` | Name | LOD 组名 | ✅ | **禁用/隐藏** |
| `one_convex_hull_per_ucx` | bool | 每 UCX 一个凸包 | ❌ | N/A |
| `distance_field_resolution_scale` | float | 距离场分辨率缩放 | ❌ | N/A |

#### SkeletalMesh 专有属性（FbxSkeletalMeshImportData）

| 属性 | 类型 | 说明 | 建议配置 | 优先级 |
|------|------|------|:--------:|:------:|
| `import_morph_targets` | bool | 导入变形目标（BlendShape） | ✅ 加入 | **高** |
| `import_meshes_in_bone_hierarchy` | bool | 导入骨骼层级中的网格 | ✅ 加入 | 高 |
| `update_skeleton_reference_pose` | bool | 更新骨骼参考姿势 | ✅ 加入 | 高 |
| `use_t0_as_ref_pose` | bool | 使用 T0 帧作为参考姿势 | ✅ 加入 | 中 |
| `preserve_smoothing_groups` | bool | 保留平滑组 | ✅ 加入 | 中 |
| `import_content_type` | FBXImportContentType | 导入内容类型 | ✅ 加入 | 中 |
| `keep_sections_separate` | bool | 保持材质段分离 | ⚠️ 可选 | 低 |
| `import_vertex_attributes` | bool | 导入顶点属性 | ⚠️ 可选 | 低 |
| `morph_threshold_position` | float | 变形目标位置阈值 | ⚠️ 可选 | 低 |
| `threshold_position` | float | 顶点位置合并阈值 | ⚠️ 可选 | 低 |
| `threshold_tangent_normal` | float | 切线法线合并阈值 | ⚠️ 可选 | 低 |
| `threshold_uv` | float | UV 合并阈值 | ⚠️ 可选 | 低 |

#### FbxImportUI 顶层 Skeletal 专有属性

| 属性 | 类型 | 说明 | 建议配置 | 优先级 |
|------|------|------|:--------:|:------:|
| `skeleton` | Skeleton | **已有骨骼资产路径**（核心需求） | ✅ 必须加入 | **最高** |
| `create_physics_asset` | bool | 自动创建物理资产 | ✅ 加入 | 高 |
| `physics_asset` | PhysicsAsset | 已有物理资产路径 | ⚠️ 可选 | 低 |

### A.4 FBXImportContentType 枚举

```python
unreal.FBXImportContentType:
    FBXICT_ALL                 # 导入几何体 + 蒙皮权重
    FBXICT_GEOMETRY            # 仅几何体（用于更新网格但保留权重）
    FBXICT_SKINNING_WEIGHTS    # 仅蒙皮权重（用于更新权重但保留几何体）
```

### A.5 Skeleton 资产路径设置方式

```python
# 使用已有骨骼
skeleton_path = "/Game/Characters/Common/SK_Mannequin_Skeleton"
skeleton = unreal.load_asset(skeleton_path)
if skeleton:
    fbx_ui.set_editor_property("skeleton", skeleton)

# 不指定 skeleton 时：FBX 导入器自动创建新 Skeleton
```

**设置代码验证**：`FbxImportUI.skeleton` 为 `Skeleton` 类型的资产引用，可通过 `unreal.load_asset()` 加载后赋值。当不指定时引擎自动从 FBX 创建新 Skeleton。✅

### A.6 配置 Schema 扩展方案

在现有 `MeshImportConfig` 中新增以下字段：

```python
@dataclass
class MeshImportConfig:
    # ... 现有字段 ...

    # ── SkeletalMesh 专有（仅 import_as_skeletal=True 时生效）──
    skeleton_path: str = ""                       # 已有 Skeleton 资产路径，空=自动创建
    create_physics_asset: bool = True             # 自动创建物理资产
    import_morph_targets: bool = True             # 导入变形目标 (BlendShape)
    import_meshes_in_bone_hierarchy: bool = True  # 导入骨骼层级中的网格
    update_skeleton_reference_pose: bool = False  # 更新骨骼参考姿势
    use_t0_as_ref_pose: bool = False              # 使用 T0 帧作为参考姿势
    preserve_smoothing_groups: bool = True        # 保留平滑组
    import_content_type: str = "All"              # "All" | "Geometry" | "SkinningWeights"
```

### A.7 JSONC 配置示例（Character Profile 扩展）

```jsonc
"mesh_import": {
    "import_uniform_scale": 1.0,
    "import_as_skeletal": true,

    // ── SkeletalMesh 专有（仅 import_as_skeletal=true 时读取）──
    "skeleton_path": "/Game/Characters/Common/SK_Mannequin_Skeleton",
    "create_physics_asset": true,
    "import_morph_targets": true,
    "import_meshes_in_bone_hierarchy": true,
    "update_skeleton_reference_pose": false,
    "use_t0_as_ref_pose": false,
    "preserve_smoothing_groups": true,
    "import_content_type": "All",

    // ── 共享 ──
    "normal_import_method": "ImportNormalsAndTangents",
    "normal_generation_method": "MikkTSpace",
    "compute_weighted_normals": true,
    "vertex_color_import_option": "Ignore",
    "import_animations": true,
    "convert_scene": true,
    "convert_scene_unit": true,

    // ── 以下 StaticMesh 专有项将被忽略 ──
    // "auto_generate_collision": false,  ← 无效
    // "build_nanite": false,             ← 无效
    // "generate_lightmap_u_vs": false,   ← 无效

    "import_materials": true,
    "import_textures": true,
    "reorder_material_to_fbx_order": true
}
```

### A.8 import_pipeline.py 改造方案

```python
def import_fbx(self, fbx_path, destination_path, ..., mesh_import=None):
    mi = mesh_import or MeshImportConfig()
    fbx_ui = unreal.FbxImportUI()

    # 共享顶层设置
    fbx_ui.set_editor_property("import_as_skeletal", mi.import_as_skeletal)
    fbx_ui.set_editor_property("import_animations", mi.import_animations)
    fbx_ui.set_editor_property("import_materials", mi.import_materials)
    fbx_ui.set_editor_property("import_textures", mi.import_textures)

    if mi.import_as_skeletal:
        # ── Skeletal 路径 ──
        if mi.skeleton_path:
            sk = unreal.load_asset(mi.skeleton_path)
            if sk:
                fbx_ui.set_editor_property("skeleton", sk)
            else:
                logger.warning(f"Skeleton 资产未找到: {mi.skeleton_path}")
        fbx_ui.set_editor_property("create_physics_asset", mi.create_physics_asset)

        sk_data = fbx_ui.get_editor_property("skeletal_mesh_import_data")
        # 共享基类属性
        sk_data.set_editor_property("import_uniform_scale", mi.import_uniform_scale)
        sk_data.set_editor_property("normal_import_method", ...)
        sk_data.set_editor_property("normal_generation_method", ...)
        sk_data.set_editor_property("compute_weighted_normals", mi.compute_weighted_normals)
        sk_data.set_editor_property("vertex_color_import_option", ...)
        sk_data.set_editor_property("convert_scene", mi.convert_scene)
        # ... 其他共享属性 ...

        # Skeletal 专有属性
        sk_data.set_editor_property("import_morph_targets", mi.import_morph_targets)
        sk_data.set_editor_property("import_meshes_in_bone_hierarchy", mi.import_meshes_in_bone_hierarchy)
        sk_data.set_editor_property("update_skeleton_reference_pose", mi.update_skeleton_reference_pose)
        sk_data.set_editor_property("use_t0_as_ref_pose", mi.use_t0_as_ref_pose)
        sk_data.set_editor_property("preserve_smoothing_groups", mi.preserve_smoothing_groups)
        sk_data.set_editor_property("import_content_type", _map_content_type(mi.import_content_type))
    else:
        # ── StaticMesh 路径（现有逻辑）──
        sm_data = fbx_ui.get_editor_property("static_mesh_import_data")
        # ... 现有设置 ...
```

### A.9 UI 编辑器改造方案

Processing Tab 中 Mesh Import Settings 面板根据 `import_as_skeletal` 复选框动态显隐控件：

```
┌─ Mesh Import Settings ──────────────────────────────────────┐
│                                                               │
│  ── 基础 ──                                                  │
│  Scale: [1.0    ]  ☑ Import as Skeletal                      │
│                                                               │
│  ┌─ SkeletalMesh 专有（仅 Skeletal 模式时可见）─────────┐    │
│  │  Skeleton Path: [/Game/Characters/.../SK_XXX    ] [📁]│    │
│  │  ☑ Create Physics Asset                               │    │
│  │  ☑ Import Morph Targets                               │    │
│  │  ☑ Import Meshes In Bone Hierarchy                    │    │
│  │  □ Update Skeleton Reference Pose                     │    │
│  │  □ Use T0 As Ref Pose                                 │    │
│  │  ☑ Preserve Smoothing Groups                          │    │
│  │  Import Content Type: [All ▼]                         │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌─ StaticMesh 专有（仅 Static 模式时可见）─────────────┐    │
│  │  ☑ Auto Generate Collision  ☑ Combine Meshes         │    │
│  │  ☑ Remove Degenerates       □ Build Nanite           │    │
│  │  ☑ Build Reversed Index     ☑ Generate Lightmap UVs  │    │
│  │  LOD Group: [None ▼]                                  │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                               │
│  ── 共享 ──                                                  │
│  Normal Import: [ImportNormalsAndTangents ▼]                 │
│  Normal Gen:    [MikkTSpace ▼]                               │
│  ☑ Compute Weighted Normals                                  │
│  Vertex Color:  [Ignore ▼]                                   │
│  □ Import Animations                                          │
│  ☑ Convert Scene  ☑ Convert Scene Unit  □ Force Front X      │
│  □ Import Mesh LODs                                           │
│  ☑ Import Materials  ☑ Import Textures                       │
│  ☑ Reorder Material to FBX Order                             │
└───────────────────────────────────────────────────────────────┘
```

**交互行为**：
- 勾选 `Import as Skeletal` → SkeletalMesh 专有区块**显示**，StaticMesh 专有区块**隐藏**
- 取消勾选 → 反之
- `Skeleton Path` 控件附带 `📁` 按钮（可输入路径或弹出资产选择器）

### A.10 改动范围评估

| 文件 | 改动内容 | 复杂度 |
|------|----------|--------|
| `core/config/schema.py` | `MeshImportConfig` 新增 8 个 Skeletal 字段 | 低 |
| `core/config/loader.py` | `_parse_mesh_import()` 新增 Skeletal 字段解析 | 低 |
| `import_pipeline.py` | `import_fbx()` 条件分支：Static vs Skeletal 路径 | **中** |
| `config_editor.py` | 动态显隐容器 + 8 个新控件 + `skeleton_path` LabeledLine | **中** |
| `Prop.jsonc` | 无需改动（`import_as_skeletal: false`） | 无 |
| `Character.jsonc` | 可选：添加 Skeletal 字段示例 | 低 |
| `test_mesh_import_config.py` | 新增 Skeletal 字段解析测试 | 低 |

### A.11 结论

**可行性：完全可行** ✅

- `FbxImportUI.skeleton` 属性可通过 `unreal.load_asset()` + `set_editor_property()` 设置已有骨骼路径
- `FbxSkeletalMeshImportData` 暴露了所有 Skeletal 专有属性，均可通过 Python API 设置
- 方案核心：schema 增加 8 字段 → loader 增加解析 → pipeline 条件分支 → UI 动态显隐
- 与现有 StaticMesh 配置完全兼容：`import_as_skeletal=false` 时 Skeletal 字段被忽略
- UI 中通过 `import_as_skeletal` 复选框的 `toggled` 信号控制两组专有控件的可见性，用户体验清晰
