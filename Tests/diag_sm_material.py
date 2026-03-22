"""诊断 SM → MI 绑定状态。

检查 /Game/Assets/Prop/TestStaticMesh 下的 SM 和 MI 是否正确绑定。
"""
import unreal

TARGET = "/Game/Assets/Prop/TestStaticMesh"
SM_PATH = f"{TARGET}/SM_TestStaticMesh"
MI_PATH = f"{TARGET}/MI_TestStaticMesh"

unreal.log("=" * 60)
unreal.log("[DIAG] SM → MI Binding Diagnostic")
unreal.log("=" * 60)

elib = unreal.EditorAssetLibrary

# 1. 检查资产是否存在
for path in [SM_PATH, MI_PATH]:
    exists = elib.does_asset_exist(path)
    unreal.log(f"[DIAG] Asset exists: {path} = {exists}")

# 2. 加载 SM 并检查材质
sm = elib.load_asset(SM_PATH)
if sm is None:
    unreal.log_error("[DIAG] SM not found!")
else:
    unreal.log(f"[DIAG] SM class: {sm.get_class().get_name()}")
    
    # static_materials
    materials = sm.get_editor_property("static_materials")
    unreal.log(f"[DIAG] static_materials count: {len(materials) if materials else 0}")
    if materials:
        for i, mat_entry in enumerate(materials):
            mat_iface = mat_entry.get_editor_property("material_interface")
            mat_name = mat_iface.get_path_name() if mat_iface else "(None)"
            slot_name = mat_entry.get_editor_property("material_slot_name")
            unreal.log(f"[DIAG]   slot[{i}]: name={slot_name}, material={mat_name}")
    else:
        unreal.log_error("[DIAG] No static_materials on SM!")

# 3. 加载 MI 并检查父材质和贴图参数
mi = elib.load_asset(MI_PATH)
if mi is None:
    unreal.log_error("[DIAG] MI not found!")
else:
    unreal.log(f"[DIAG] MI class: {mi.get_class().get_name()}")
    parent = mi.get_editor_property("parent")
    unreal.log(f"[DIAG] MI parent: {parent.get_path_name() if parent else '(None)'}")
    
    # texture_parameter_values
    tex_params = mi.get_editor_property("texture_parameter_values")
    unreal.log(f"[DIAG] MI texture params count: {len(tex_params)}")
    for tp in tex_params:
        info = tp.get_editor_property("parameter_info")
        param_name = info.get_editor_property("name") if info else "?"
        tex_val = tp.get_editor_property("parameter_value")
        tex_path = tex_val.get_path_name() if tex_val else "(None)"
        unreal.log(f"[DIAG]   param={param_name}, texture={tex_path}")

unreal.log("=" * 60)
unreal.log("[DIAG] Done")
unreal.log("=" * 60)
