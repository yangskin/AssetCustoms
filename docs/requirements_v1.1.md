# 需求规格（V1.1 / Config v1.1）

版本: V1.1 (Config v1.1)  
状态: 需求已确认  
负责人: (您的名字/TA团队)  
最后更新: 2025年11月11日

> **注意**：Config v2.0 三段式管线模型已设计确认，将取代 v1.1 扁平配置结构。详见 [ADR-0002](./decisions/ADR-0002-config-v2-pipeline-model.md)。本文档保留 v1.1 需求作为历史参考。

---

## 1. 愿景（Product Vision）
AssetCustoms 是一个 Unreal Engine 编辑器插件，定位为项目资产管线的“标准化守门员（Standardization Goalkeeper）”。工具消除外部资产（AIGC、Sketchfab、Turbosquid 等）与项目内部标准之间的鸿沟，以“静默成功，响亮失败”的 UX 模型，一键转化为生产就绪资产。

V1.1 核心目标：在多管线（角色、场景等）下，100% 自动化命名、PBR 贴图打包、材质实例（MIC）创建、贴图导入设置（压缩、LOD 组、sRGB、VT）。

## 2. 目标用户与用户故事
- 主要用户：
  - 美术（场景/角色/道具）：10 秒内以“Prop”规范导入外部模型，自动重命名、打包 MRO、创建 MI、设置法线贴图压缩。
  - 关卡设计师：快速填充场景验证布局与美术风格。
- 次要用户：
  - 技术美术（TA）：为不同管线（Character/Prop）创建独立配置文件（Character.jsonc、Prop.jsonc），美术仅需选择 Profile 即可执行复杂规则，确保合规。

## 3. 核心痛点（Problem Statement）
- P-5：管线僵化（Inflexibility）——配置需支持多专业、多 Profile。
- P-6：导入设置繁琐（Import Settings）——自动设置贴图压缩、LOD 组、sRGB 等，避免人工出错。

## 4. 核心用户流程（Core UX Flow - V1.1）
- 触发：在内容浏览器中选择目标目录；点击“AssetCustoms: 智能导入 ▼”；从下拉中选择 Profile（Prop/Character）。
- 选择：文件对话框选择 .fbx。
- 后台：计算隔离区路径 /Game/.../_temp_{BaseName}/ 并导入 FBX 与贴图；触发检查链（FR3）。
- 分支 A（静默成功）：检查全部通过 -> 标准化引擎执行贴图处理、重命名/移动、创建并链接 MIC、应用导入设置、清理隔离区 -> 成功通知。
- 分支 B（响亮失败）：检查失败 -> 停止破坏性操作、保留隔离区 -> 弹出分诊 UI，展示原因并预填，用户补全缺失映射 -> 执行引擎 -> 完成。

## 5. 功能需求（Functional Requirements - V1.1）

### FR 1：TA 配置系统（Config）
1.1 配置档案目录：启动时扫描 TA 定义目录（如 /Content/Config/AssetCustoms/）。

1.2 Profile 加载：该目录下的每个 .jsonc/.json 视为独立 Profile；文件基础名（Prop.jsonc -> “Prop”）作为 UI 名称。

1.3 Profile 结构：每个配置文件必须遵循 v1.1 结构（见附录 A）。

1.4 配置文件内容（v1.1）：
- config_version：必须存在。
- default_master_material_path：默认主材质 UE 路径；为空表示不创建材质实例。
- default_fallback_import_path：默认回退路径。
- target_path_template（新）：最终资产落地目录模板（支持 {Name}, {Category}）。
- conflict_policy（新）：命名冲突策略（overwrite, skip, version）。
- asset_naming_template：最终 UE 资产命名模板。
- asset_subdirectories（新）：可选的资产类型子目录映射（static_mesh / material_instance / texture），空字符串表示放在 target_path 根目录。
- texture_input_rules（新）：输入识别规则（match_mode, priority, patterns 等）。
- texture_output_definitions（新）：输出处理定义（channels 数学、import_settings 等）。

1.5 JSONC 解析（新）：Python 必须能解析 .jsonc；优先内置 json5，或剥离注释后解析。

> 实现状态快照（2025-11-11）：
> - 已实现：JSONC 解析（优先 json5，回退注释剥离+尾逗号）；默认 Profile 示例（Prop.jsonc）；Unreal 侧 Profile 扫描并注入下拉菜单。
> - 已实现（核心）：`load_config()` 数据类输出（当前覆盖 texture_merge、allowed_modes）。
> - 待实现：Schema v1.1 全量字段（target_path_template、conflict_policy、texture_input_rules、texture_output_definitions 等）的解析与校验。

### FR 2：“智能导入”核心流程（Import Core）
2.1 UI 入口：内容浏览器工具栏新增下拉按钮“AssetCustoms: 智能导入 ▼”，下拉动态填充 Profile 名称。

2.2 文件选择：点击某 Profile 后，加载配置，随后打开 .fbx 文件选择对话框。

2.3 隔离区路径计算：从内容浏览器读取当前路径 Current_Path、获取 Base_Name、计算 Isolation_Path = {Current_Path}/_temp_{Base_Name}/；Current_Path 无效则用 default_fallback_import_path。

2.3.1 Base_Name 提取规则（`extract_base_name`）：
- 唯一来源为模型文件名（不从贴图、材质或其他信息推导）。
- 去扩展名后，剥离已知 UE 前缀（`SM_`/`SK_`/`T_`/`MI_`/`M_`）。
- 可读性判定：名称 ≤ 40 字符且不含 UUID 片段（连续 8+ 位 hex）→ 直接使用。
- 不可读（AIGC UUID 乱码、Tripo / Meshy 导出等）→ 截取原始文件名（含前缀、去扩展名）前 12 字符（不足 12 全用），并去除末尾 `_`/`-`。
- 示例：`tripo_convert_07eaa50d-9af7-4391-aefb-6e4ec42ec7b1.fbx` → `tripo_conver`。
- 后续所有命名模板（SM/MI/Texture/目标路径）均以此 Base_Name 为 `{Name}` 占位符值。

2.4 自动化导入：配置 FbxImportUi（import_textures = True）；根据 texture_input_rules.search_roots 配置贴图搜索路径；调用 AssetTools 将 FBX 与关联贴图导入到 Isolation_Path。

2.5 触发检查：导入成功后自动触发 FR3 并传入 Selected_Profile。

> 实现状态快照（2025-11-11）：
> - 已实现：工具栏“AssetCustoms ▼”下拉（动态 Profile）；文件对话框（tkinter，仅 .fbx，多选）；构建 ImportContext（解析 Profile + 采样 Content Browser 路径）。
> - 待实现：隔离区导入流程（FBX+纹理）与贴图搜索；后续检查链对接。

### FR 2.5：原生嵌入贴图管线（Native Embedded Texture Pipeline）

**背景**：AIGC 模型（Tripo AI、Meshy 等）的 FBX 文件通常将贴图嵌入文件内部，而非作为外部文件提供。UE 导入此类 FBX 时会自动提取 Texture2D + 创建临时材质。

**触发条件**：磁盘搜索（FR3 贴图映射）发现 0 张外部贴图，但 UE 隔离区中存在导入的 Texture2D 资产。

**处理流程**：

2.5.1 资产盘点：列出隔离区中所有 Texture2D 和自动创建的材质资产。

2.5.2 删除自动材质：FBX 自动创建的 Material/MaterialInstanceConstant 无法满足项目规范，予以删除。

2.5.3 贴图匹配（三层策略叠加）：
- 策略 1（名称匹配）：将 UE 资产名构造为虚拟文件名，复用 texture_input_rules 的 glob/regex 匹配。
- 策略 2（sRGB 启发式）：未匹配的贴图按 sRGB 属性分配（sRGB=True → BaseColor，sRGB=False → Normal）。
- 策略 3（单贴图兜底）：仅 1 张嵌入贴图且无匹配结果时，默认分配到 BaseColor。

2.5.4 贴图重命名：按 asset_naming_template（`T_{Name}_{Suffix}`）重命名并移动到目标路径。

2.5.5 贴图导入设置：根据匹配到的 output_definition 应用 compression、LOD group、sRGB、VT 等设置。

2.5.6 后续处理：移动 StaticMesh → 创建 MI → 链接贴图到 MI 参数 → 绑定 SM → 清理隔离区。

**与标准管线的关键差异**：
- 跳过 Pillow 通道编排（FR5.1）— 贴图保留 UE 原生导入质量。
- 跳过 FR3 检查链 — 改为内部简化检查 + 匹配。
- 无 MRO 打包 — 嵌入贴图通常只有 BaseColor，不做通道合并。

> 实现状态快照（2026-03-22）：
> - 已实现：完整原生嵌入管线（`_run_native_embedded_pipeline`）；三层匹配策略；E2E 测试通过。
> - `UnrealAssetOps` 新增方法：`delete_asset()`、`discover_imported_materials()`、`get_texture_srgb()`。

### FR 3：自动化检查链（Silent Check Chain）
3.1 资产识别：Isolation_Path 中必须有且仅有 1 个 StaticMesh；否则失败。

3.2 主材质检查：default_master_material_path 为空则视为通过且跳过 5.3；不为空但找不到资产则失败。

3.3 贴图映射（升级）：
- 目标：为所有 enabled: true 的输出项填满 channels 所需逻辑源（BaseColor、Roughness 等）。
- 尝试 A（高优先级）：读取 FBX 自动生成材质节点并“智能预填充”。
- 尝试 B（低优先级）：对未映射槽使用规则匹配（regex/glob + priority）。
- 失败条件：映射不完整，或存在“孤儿”贴图 -> 失败。

3.4 成功：3.1-3.3 全部通过则进入 FR5。

### FR 4：“响亮失败”分诊 UI（Triage UI）
- 仅在 FR3 失败时自动弹出；顶部红色文本显示失败原因（包含 Profile）。
- 自动预填识别项；为未映射槽提供下拉菜单（候选为孤儿贴图）；提供 Base_Name 文本框；提供“执行标准化”按钮触发 FR5。
> 实现状态快照（2026-03-22）：
> - 已实现：`core/pipeline/triage_ui.py` — PySide6 分诊窗口（TriageWindow + TriageDecision）
>   - 错误标题（红色 ✖ badge）、BaseName 编辑框、贴图映射表（QTableWidget + QComboBox）、孤儿提示、执行/取消按钮、UE 暗色主题
> - 已实现：`import_pipeline.py` — TriageContext 打包管线中间状态 + `resume_after_triage()` 用修正映射继续 FR5
> - 已实现：`actions.py` — `_show_triage_ui()` 集成，FR3 失败自动弹出
> - 测试：8 项单元测试 + UE 编辑器内视觉验证通过
### FR 5：标准化执行引擎（Standardization Engine）
5.1 贴图处理器：使用 Pillow；遍历 enabled 输出项；内存中创建新贴图，按 channels 定义填充像素；支持 invert/remap/constant；法线可 flip_green；可选 resize；按 file_format/bit_depth 保存到 Isolation_Path。

5.2 资产重命名/移动：使用 EditorAssetLibrary.rename_asset()；根据 target_path_template 计算最终路径；遵循 conflict_policy；按 asset_naming_template 和 suffix 命名；根据 asset_subdirectories 将 SM/MI/贴图分别放入对应子目录；将 StaticMesh 与新贴图从 Isolation_Path 移动到最终路径。

5.3 材质实例创建（MIC）：default_master_material_path 为空则跳过；否则在最终路径创建 MI_{Name}，父级设为 default_master_material_path，并按 material_parameter 自动链接新贴图。

5.4 资产链接：将 SM_{Name} 的材质槽设置为 MI_{Name}（若 5.3 未跳过）。

5.5 清理：安全删除 Isolation_Path（包含原始贴图与 FBX 自动创建的 M_...）。

5.6 应用导入设置（新）：新贴图导入/移动后，读取 Texture 资产并应用对应 import_settings（compression、lod_group、srgb、virtual_texture 等），并保存。

> 实现状态快照（2025-11-11）：
> - 已实现（核心库）：`core.textures.layer_merge.merge_layers` 支持多种混合模式与不透明度，numpy 快路径 + Pillow 回退。
> - 待实现：Unreal 像素桥接与资产写回、命名与移动、MIC 创建/链接、导入设置应用与清理。

## 6. 非功能性需求（NFR）
- NFR1 性能：典型资产“静默成功”全流程 ≤ 5 秒。
- NFR2 依赖：内置 Pillow（PIL）与 JSONC 解析能力（json5 或注释剥离）。
- NFR3 健壮性：失败时停止在隔离区，记录清晰日志，不崩溃编辑器。
- NFR4 可配置性：未发现任何 .jsonc/.json 配置时，入口按钮需明确提示“配置失败”并禁用点击。
 - NFR5 提交控制：默认禁止自动提交到 GitHub；仅在收到显式授权时方可执行提交/推送。

### NFR-AC-01 禁止自动提交到 GitHub

- 默认不执行 `git commit` 与 `git push`。
- 仅在收到“显式授权提示词”（例如“请提交到 GitHub”“执行 Git 提交并推送”）时，脚本或工具才可代表用户执行提交/推送。
- 必须记录日志：包含触发内容、确认人/确认方式与时间戳，便于审计。

## 7. 附录（Appendix）
### 附录 A：TA 配置文件示例（Prop.jsonc）

```jsonc
{
  // === AssetCustoms（守门员）配置 v1.1（JSON with Comments）===
  // 注意：
  // 1) UE的Python环境可能没有 `json5` 库，建议TA保存为“无注释的.json”或工具自行剥离注释。
  // 2) {占位符} 将在运行时替换：{Name} {Suffix} {Category} {UDIM} {Frame} {DropDir}

  "config_version": "1.1",

  // 可为空字符串 "" 表示“不自动创建材质实例”
  "default_master_material_path": "/Game/MyProject/Materials/Masters/MM_Prop_PBR.MM_Prop_PBR",

  // 默认落地路径（当 target_path_template 计算失败时使用）
  "default_fallback_import_path": "/Game/AIGC_Dropoff",

  // UE 资产落地目录模板（建议按品类/资产名分桶）
  // {Category} 来自 Profile 文件名 (例如 "Prop")
  "target_path_template": "/Game/Assets/{Category}/{Name}",

  // 命名冲突策略：overwrite | skip | version（自动追加 _001, _002…）
  "conflict_policy": "version",

  // 资产命名模板（仅影响导入后的 UE 资产名）
  "asset_naming_template": {
    "static_mesh": "SM_{Name}",
    "material_instance": "MI_{Name}",
    "texture": "T_{Name}_{Suffix}"
  },

  // 资产子目录（可选，空字符串=放在同级目录）
  "asset_subdirectories": {
    "static_mesh": "",
    "material_instance": "Materials",
    "texture": "Textures"
  },

  // === 输入识别规则（从投放目录里把文件匹配到“逻辑位”） ===
  "texture_input_rules": {
    // 匹配模式：glob | regex
    "match_mode": "glob",
    // 大小写不敏感
    "ignore_case": true,
    // 允许的文件扩展名（建议覆盖你团队常用格式）
    "extensions": [".png", ".tga", ".jpg", ".jpeg", ".exr", ".tif", ".tiff"],
    // 搜索根目录（{DropDir} 为FBX所在的目录）
    "search_roots": [
      "{DropDir}",
      "{DropDir}/Textures",
      "{DropDir}/Maps"
    ],
    // 逻辑位 → 匹配模式（按 priority 取最优命中；多命中时进入分诊/或按优先级取一个）
    "rules": {
      "BaseColor":        { "priority": 10, "patterns": ["*_bc*", "*_diffuse*", "*_d*", "*_albedo*"] },
      "Normal":           { "priority": 10, "patterns": ["*_n*", "*_normal*", "*_nrm*"] },
      "Roughness":        { "priority": 9,  "patterns": ["*_r*", "*_rough*", "*_roughness*"] },
      "Metallic":         { "priority": 9,  "patterns": ["*_m*", "*_metal*", "*_metallic*"] },
      "AmbientOcclusion": { "priority": 8,  "patterns": ["*_ao*", "*_ambientocclusion*"] },
      "Height":           { "priority": 7,  "patterns": ["*_h*", "*_height*", "*_displacement*"] }

      // —— 非 PBR 示例：按需开启 —— //
      // "UI":            { "priority": 5,  "patterns": ["*ui_atlas*"] },
      // "Flow":          { "priority": 5,  "patterns": ["*flow*", "*vec*"] },
      // "Mask_A":        { "priority": 5,  "patterns": ["*edge*", "*ao_mask*"] },
      // "Mask_B":        { "priority": 5,  "patterns": ["*wetness*"] },
      // "Mask_C":        { "priority": 5,  "patterns": ["*dust*"] }
    }
  },

  // === 输出贴图定义（任意通道编排；不仅限于 PBR） ===
  // 每个输出：是否启用、命名后缀、色彩空间、位深、是否生成 Mip、通道映射、UE 导入属性…
  "texture_output_definitions": [
    {
      // --- 漫反射 ---
      "enabled": true,
      "output_name": "Diffuse",
      "suffix": "D",
      "category": "PBR",
      "srgb": true,                 // (此标记将用于 import_settings)
      "file_format": "PNG",         // PNG | TGA | EXR
      "bit_depth": 8,               // 8 | 16（EXR 时可忽略）
      "mips": true,                 // (此标记将用于 import_settings)
      "resize": null,               // 例如 { "width": 2048, "height": 2048 }；null 表示不缩放
      "alpha_premultiplied": false, // (暂V1.0不实现, V2.0 Pillow处理)
      "material_parameter": "BaseColor_Texture",
      "channels": {
        // 每个通道可指定：from（逻辑源名）ch（R/G/B/A） invert（布尔） gamma（数值）
        // remap：[inMin, inMax, outMin, outMax]；constant：常量值（当无源时兜底）
        "R": { "from": "BaseColor", "ch": "R" },
        "G": { "from": "BaseColor", "ch": "G" },
        "B": { "from": "BaseColor", "ch": "B" },
        "A": { "constant": 1.0 }
      },
      "import_settings": {
        "compression": "TC_Default",
        "lod_group": "TEXTUREGROUP_World",
        "virtual_texture": false,
        "address_x": "Wrap",
        "address_y": "Wrap",
        "mip_gen": "FromTextureGroup"
      }
    },

    {
      // --- 法线 ---
      "enabled": true,
      "output_name": "Normal",
      "suffix": "N",
      "category": "PBR",
      "srgb": false,
      "file_format": "PNG",
      "bit_depth": 8,
      "mips": true,
      "material_parameter": "Normal_Texture",
      // DCC/引擎坐标差异控制：OpenGL | DirectX；flip_green true 表示 Y 通道取反
      "normal_space": "OpenGL",
      "flip_green": true,
      "channels": {
        "R": { "from": "Normal", "ch": "R" },
        "G": { "from": "Normal", "ch": "G" },
        "B": { "from": "Normal", "ch": "B" }, // B通道将由Pillow自动计算或保留
        "A": { "constant": 1.0 }
      },
      "import_settings": {
        "compression": "TC_Normalmap",
        "lod_group": "TEXTUREGROUP_WorldNormalMap",
        "virtual_texture": false,
        "address_x": "Wrap",
        "address_y": "Wrap",
        "mip_gen": "FromTextureGroup"
      }
    },

    {
      // --- 金属/粗糙/AO 打包（MRO）---
      "enabled": true,
      "output_name": "Packed_MRO",
      "suffix": "MRO",
      "category": "PBR",
      "srgb": false,
      "file_format": "PNG",
      "bit_depth": 8,
      "mips": true,
      "material_parameter": "Packed_Texture",
      // 允许缺项：缺失时按各通道的 constant 兜底
      "allow_missing": true,
      "channels": {
        // (假设源贴图都是灰度图, 统一用 'R' 通道)
        "R": { "from": "Metallic",         "ch": "R", "constant": 0.0 },
        "G": { "from": "Roughness",        "ch": "R", "constant": 0.5 },
        "B": { "from": "AmbientOcclusion", "ch": "R", "constant": 1.0 },
        "A": { "constant": 1.0 }
      },
      "import_settings": {
        "compression": "TC_Masks", // (或 TC_Default, 取决于管线)
        "lod_group": "TEXTUREGROUP_World",
        "virtual_texture": false,
        "address_x": "Wrap",
        "address_y": "Wrap",
        "mip_gen": "FromTextureGroup"
      }
    },

    {
      // --- 高度 ---
      "enabled": true,
      "output_name": "Height",
      "suffix": "H",
      "category": "PBR",
      "srgb": false,
      "file_format": "PNG",
      "bit_depth": 16, // 高度/位移建议 16 位
      "mips": true,
      "material_parameter": "Height_Texture",
      "channels": {
        // 如源是灰度，可三通道同源；可按需 remap
        "R": { "from": "Height", "ch": "R", "remap": [0.0, 1.0, 0.0, 1.0], "constant": 0.0 },
        "G": { "from": "Height", "ch": "R", "constant": 0.0 },
        "B": { "from": "Height", "ch": "R", "constant": 0.0 },
        "A": { "constant": 1.0 }
      },
      "import_settings": {
        "compression": "TC_Grayscale", // (或 TC_Masks)
        "lod_group": "TEXTUREGROUP_World",
        "virtual_texture": false,
        "address_x": "Wrap",
        "address_y": "Wrap",
        "mip_gen": "FromTextureGroup"
      }
    }

    // --- 可选：非 PBR 示例，按需启用 ---
    // ( ... 更多自定义打包规则 ... )
  ]
}
```

---

- 规格约束与 Schema 细节建议在实现阶段用 JSON Schema 或 pydantic（若环境允许）校验；也可自定义轻量校验器。
- 对“智能预填充”的材质节点分析，建议收集实际项目示例以完善映射策略。
- 性能与健壮性需要在真实资产样本上压测与故障注入验证。
