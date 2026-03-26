# ADR-0006: Level Editor 选中 Actor → Send to Substance Painter

**状态**: 已确认  
**日期**: 2026-03-26  
**关联**: ADR-0004（Send to SP 基础架构）、M7（Content Browser 发送流程）

## 背景

当前 Send to Substance Painter 功能仅支持从 Content Browser 选中 StaticMesh/SkeletalMesh 资产右键发送。
用户在 Level Editor 中选中场景 Actor 时，需要手动找到对应的 StaticMesh 资产再操作。

**需求**：在 Level Editor 中选中含 StaticMeshComponent 的 Actor，直接提取绑定的 StaticMesh 资产发送到 SP。

## 可行性调查

### API 链路（全部确认可用于 UE 5.7 Python API）

| 步骤 | API | 返回类型 |
|------|-----|----------|
| 1. 获取选中 Actor | `EditorActorSubsystem.get_selected_level_actors()` | `Array[Actor]` |
| 2. 提取 StaticMeshComponent | `Actor.get_components_by_class(StaticMeshComponent)` | `Array[ActorComponent]` |
| 3. 获取 StaticMesh 资产 | `StaticMeshComponent.static_mesh` (只读属性) | `StaticMesh` |
| 4. 获取资产路径 | `Object.get_path_name()` | `str` |
| 5. 导出 FBX | `Exporter.run_asset_export_task(AssetExportTask)` | `bool` |

### 与现有流程对接

现有 `SPBridge._send_selected_impl()` 的 mesh 获取逻辑：
```python
assets = unreal.EditorUtilityLibrary.get_selected_assets()  # Content Browser
mesh = next((a for a in assets if isinstance(a, (StaticMesh, SkeletalMesh))), None)
```

新增 Level Editor 入口只需在获取 mesh 的步骤前加一层"从 Actor 解包 StaticMesh"逻辑，
后续所有步骤（收集材质、导出 FBX/贴图、发送到 SP）完全复用。

### 概念验证伪代码

```python
import unreal

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_selected_level_actors()

meshes = []
for actor in actors:
    comps = actor.get_components_by_class(unreal.StaticMeshComponent)
    for comp in comps:
        mesh = comp.static_mesh
        if mesh and mesh not in meshes:
            meshes.append(mesh)

# meshes 为去重后的 StaticMesh 列表，可直接传入 SPBridge 后续流程
```

## 决策

### 实现方案

修改 `SPBridge._send_selected_impl()` 增加 Level Editor 选中 Actor → StaticMesh 的提取逻辑：

1. **优先 Content Browser**：若 Content Browser 有选中的 StaticMesh/SkeletalMesh，沿用现有逻辑。
2. **回退 Level Editor**：若 Content Browser 无选中，尝试从 Level Editor 选中的 Actor 提取 StaticMesh。
3. **多 Actor / 多组件策略**：提取所有 Actor 的第一个 StaticMeshComponent 的 StaticMesh，
   若有多个不同 mesh，仅发送第一个（后续可扩展为批量发送）。

### UI 注册

- Content Browser 右键菜单条目保持不变（`Send > Send to Substance Painter`）。
- **新增**：Level Editor 视口 Actor 右键菜单注册 `Send > Send to Substance Painter`。
  - 菜单路径：`LevelEditor.ActorContextMenu` → `ActorOptions` section → `Send` 子菜单
  - 回调复用同一个 `on_send_to_substance_painter()` action，内部自动探测输入来源。

### 风险与限制

| 风险 | 缓解 |
|------|------|
| 多个不同 StaticMesh | 当前仅发送第一个，日志提示用户 |
| Actor 无 StaticMeshComponent | 弹窗提示"未找到 StaticMesh" |
| Blueprint Actor 嵌套子组件 | `get_components_by_class` 自动包含子组件 |
| SkeletalMeshComponent | 当前不处理（仅扩展 StaticMesh） |

## 实施计划

- **修改文件**：
  - `sp_bridge.py` — `_send_selected_impl()` 增加 Level Editor 回退逻辑 + `_extract_mesh_from_selected_actors()` 新方法
  - `ui.py` — 新增 `_register_actor_context_menu()` 在 `LevelEditor.ActorContextMenu` 注册菜单
- **测试**：
  - 🤖 pytest：mock `EditorActorSubsystem` 验证提取逻辑（9 passed）
  - 👁️ UE 人工：Level Editor 选中 Actor → 右键菜单 Send → Send to SP → 确认正确 mesh 被发送
  - 兼容性：Content Browser 选中仍优先走原路径，不影响现有功能
