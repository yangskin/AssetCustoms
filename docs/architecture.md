# 系统架构 / 模块边界 / 数据流（V1.1）

本项目位于 Unreal Engine 插件的 Python 侧，主要用于资源处理与工具自动化，围绕“静默成功，响亮失败”的 UX 模型构建。

## 作用域与边界
- 边界：仅覆盖 UE Python 脚本与其交互的最小外部接口（Editor、AssetTools、EUL、材质系统、文件对话框）。
- 非目标：不直接修改 UE C++ 核心；不引入重量级依赖（Pillow、json5 属于轻依赖并随插件内置）。

## 顶层视图（模块概览）
- 入口：`init_unreal.py`
  - 初始化日志与异常捕获；注册“内容浏览器工具栏下拉按钮”。
  - 扫描配置目录，加载 Profile（JSON/JSONC）。
- 模块 A：Profile/配置管理（FR1）
  - 扫描目录、解析 JSONC、校验 config_version 与 Schema v1.1。
  - 暴露 Profile 列表供 UI 填充；提供占位符替换工具（{Name}/{Category}/{DropDir} 等）。
- 模块 B：“智能导入”入口（FR2）
  - 内容浏览器工具栏下拉按钮，动态填充 Profile。
  - 在选择 Profile 后带上下文文件选择（.fbx），计算“隔离区”路径并导入 FBX+纹理。
- 模块 C：自动化检查链（FR3）
  - 检查模型数量（仅 1 个 StaticMesh）。
  - 主材质可用性检查（允许空路径跳过 MIC）。
  - 贴图映射：优先从 FBX 材质节点“智能预填充”，其次应用规则匹配（glob/regex+priority）。
- 模块 D：分诊 UI（FR4）
  - 仅在检查失败时弹出；展示失败原因、已识别结果；对未映射槽提供下拉选择；支持 Base_Name 确认；触发执行。
- 模块 E：标准化执行引擎（FR5）
  - 贴图处理（Pillow）：通道编排、常量/反相/remap、normal G 反转、可选缩放、格式/位深保存。
  - 资产重命名与移动：根据 target_path_template、asset_naming_template、conflict_policy 实施。
  - 材质实例创建与链接：父材质=default_master_material_path，参数按定义自动绑定。
  - 资产链接与清理：SM 绑定 MI；清理隔离区；应用导入设置（压缩、LOD 组、sRGB、VT 等）。

## 数据流（时序）
1) UE 加载插件 -> `init_unreal.py` 注册 UI 与加载 Profile 列表。
2) 用户选择“AssetCustoms: 智能导入 ▼”中的某 Profile -> 打开 .fbx 文件对话框。
3) 计算隔离区路径，导入 FBX 与纹理（按 search_roots）。
4) 触发检查链：模型数量 -> 主材质 -> 贴图映射（智能预填充 + 规则匹配）。
5) 分支：
   - 成功：进入标准化引擎（贴图处理、重命名/移动、MIC 创建/链接、导入设置、清理）-> 通知成功。
   - 失败：保留隔离区并弹出分诊 UI -> 用户补全 -> 再次执行标准化引擎。

## 目录结构（当前）
```
AssetCustoms/                      # 插件根目录（当前仓库根）
  ├─ AssetCustoms.uplugin          # Unreal 插件描述文件
  ├─ Content/
  │   └─ Python/
  │       └─ init_unreal.py        # UE Python 入口脚本
  ├─ docs/                         # 项目文档
  │   ├─ architecture.md
  │   ├─ requirements_v1.1.md
  │   ├─ roadmap.md
  │   └─ decisions/
  │       └─ ADR-0001.md
  ├─ standards/                    # 规范与指南
  │   ├─ coding-style.md
  │   ├─ review-checklist.md
  │   └─ commit-convention.md
  ├─ README.md                     # 文档索引与导航（根级）
  ├─ CONTRIBUTING.md               # 贡献指南（根级）
  └─ SECURITY.md                   # 安全策略（根级）
```

## 模块契约（摘要）
- 配置管理（FR1）
  - 输入：配置目录路径；JSON/JSONC 文件。
  - 输出：Profile 列表与解析后的配置对象；Schema 校验结果。
  - 错误：无配置或解析失败 -> 在 UI 禁用入口并提示（NFR4）。
- 智能导入（FR2）
  - 输入：Profile 选择、当前内容浏览器路径、FBX 文件路径。
  - 输出：隔离区内的导入资产（SM、Textures、FBX 材质）。
  - 错误：Current_Path 非法 -> 使用 default_fallback_import_path。
- 检查链（FR3）
  - 输入：隔离区资产、Selected_Profile。
  - 输出：映射结果（逻辑槽 -> 源贴图）。
  - 错误：数量不符/主材质缺失/映射不完整或歧义 -> 分诊 UI。
- 分诊 UI（FR4）
  - 输入：失败原因与部分映射；孤儿贴图列表。
  - 输出：用户补全后的映射与 Base_Name 确认。
- 标准化引擎（FR5）
  - 输入：映射、Selected_Profile、Base_Name、隔离区路径。
  - 输出：最终路径中的标准化资产（SM/Textures/MIC）；导入设置已应用。
  - 错误：任何步骤失败 -> 停止、记录日志、保留隔离区（NFR3）。

## 性能与扩展
- 性能预算：典型资产从导入到清理 ≤ 5s（NFR1）。
- I/O 最小化：尽量内存中合成贴图，批量保存；避免不必要的磁盘往返。
- 可扩展性：Profile Schema 向后兼容；规则扩展不破坏现有配置。

## 参考
- 路线图：[docs/roadmap.md](./roadmap.md)
- 需求规格（V1.1）：[./requirements_v1.1.md](./requirements_v1.1.md)
- 编码规范（Google Python）：[../standards/coding-style.md](../standards/coding-style.md)
