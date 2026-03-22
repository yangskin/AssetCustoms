"""直接测试 set_static_mesh_material 的不同方法。"""
import unreal

SM_PATH = "/Game/Assets/Prop/TestStaticMesh/SM_TestStaticMesh"
MI_PATH = "/Game/Assets/Prop/TestStaticMesh/MI_TestStaticMesh"

elib = unreal.EditorAssetLibrary

mesh = elib.load_asset(SM_PATH)
mi = elib.load_asset(MI_PATH)

unreal.log(f"[TEST] mesh={mesh is not None}, mi={mi is not None}")

if mesh and mi:
    # 方法 1: get/set static_materials 数组
    materials = mesh.get_editor_property("static_materials")
    unreal.log(f"[TEST] materials type={type(materials)}, len={len(materials)}")
    
    if materials and len(materials) > 0:
        entry = materials[0]
        unreal.log(f"[TEST] entry type={type(entry)}")
        unreal.log(f"[TEST] entry.material_interface BEFORE = {entry.get_editor_property('material_interface')}")
        
        entry.set_editor_property("material_interface", mi)
        unreal.log(f"[TEST] entry.material_interface AFTER set = {entry.get_editor_property('material_interface')}")
        
        mesh.set_editor_property("static_materials", materials)
        
        # 验证写回
        materials2 = mesh.get_editor_property("static_materials")
        mat2 = materials2[0].get_editor_property("material_interface")
        unreal.log(f"[TEST] After set_editor_property writeback: {mat2}")
        
        if mat2 is None:
            # 方法 2: 尝试用 set_material 方法
            unreal.log("[TEST] Writeback failed, trying StaticMesh.set_material()")
            try:
                mesh.set_material(0, mi)
                materials3 = mesh.get_editor_property("static_materials")
                mat3 = materials3[0].get_editor_property("material_interface")
                unreal.log(f"[TEST] After set_material: {mat3}")
            except Exception as e:
                unreal.log_error(f"[TEST] set_material failed: {e}")
            
            # 方法 3: 构建新的 FStaticMaterial
            unreal.log("[TEST] Trying construct new FStaticMaterial...")
            try:
                new_entry = unreal.StaticMaterial()
                new_entry.set_editor_property("material_interface", mi)
                new_entry.set_editor_property("material_slot_name", entry.get_editor_property("material_slot_name"))
                new_materials = unreal.Array(unreal.StaticMaterial)
                new_materials.append(new_entry)
                mesh.set_editor_property("static_materials", new_materials)
                
                materials4 = mesh.get_editor_property("static_materials")
                mat4 = materials4[0].get_editor_property("material_interface")
                unreal.log(f"[TEST] After new FStaticMaterial: {mat4}")
            except Exception as e:
                unreal.log_error(f"[TEST] Construct failed: {e}")
        
        elib.save_asset(SM_PATH)
        
        # 最终确认
        mesh_final = elib.load_asset(SM_PATH)
        materials_final = mesh_final.get_editor_property("static_materials")
        mat_final = materials_final[0].get_editor_property("material_interface")
        unreal.log(f"[TEST] FINAL after save+reload: {mat_final}")
