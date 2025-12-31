import bpy

def apply_binary_weights(mesh_obj, armature_obj, target_bone_names=None, from_weight_paint=False):
    """
    Applies binary weights (0.0 or 1.0) using Auto Weights (Heat) + Limit Total.
    Includes robust context switching to avoid poll() errors.
    """
    original_mode = bpy.context.mode
    
    restore_deform_settings = []
    try:
        # Manage 'Selected Bones Only' logic by isolating deform bones
        if target_bone_names and not from_weight_paint:
            for bone in armature_obj.data.bones:
                if bone.name in target_bone_names:
                    if not bone.use_deform:
                        restore_deform_settings.append((bone, False))
                        bone.use_deform = True
                else:
                    if bone.use_deform:
                        restore_deform_settings.append((bone, True))
                        bone.use_deform = False

        # --- PATH 1: Called from Weight Paint Mode ---
        if from_weight_paint:
            # 1. Calculate Auto Weights using only the isolated deform bones
            # This operates on the whole mesh but is a necessary starting point.
            # 1. Prepare selection mask
            # We switch to Edit and back to ensure the vertex selection is a valid mask.
            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')

            # 2. Calculate Auto Weights using only the isolated deform bones
            try:
                bpy.ops.paint.weight_from_bones(type='AUTOMATIC')
            except RuntimeError:
                print("ERROR: Bone Heat Weighting failed. Check mesh geometry.")
                return {'HEAT_FAILED'}
            
            # 3. Process weights (Binarize)
            bpy.ops.object.vertex_group_limit_total(limit=1)
            bpy.ops.object.vertex_group_clean(group_select_mode='ALL', limit=0.5)
            bpy.ops.object.vertex_group_normalize_all(lock_active=False)

        # --- PATH 2: Called from Object Mode ---
        else:
            # 1. Setup selection for parenting
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            mesh_obj.select_set(True)
            armature_obj.select_set(True)
            bpy.context.view_layer.objects.active = armature_obj
            
            existing_mod_names = {m.name for m in mesh_obj.modifiers if m.type == 'ARMATURE'}

            # 2. Parent and calculate Auto Weights (Heat)
            try:
                bpy.ops.object.parent_set(type='ARMATURE_AUTO')
            except RuntimeError:
                print("ERROR: Bone Heat Weighting failed. Check mesh geometry.")
                return {'HEAT_FAILED'}

            # Clean up duplicate modifiers if one already existed
            new_mods = [m for m in mesh_obj.modifiers if m.type == 'ARMATURE' and m.name not in existing_mod_names]
            if existing_mod_names and new_mods:
                for mod in new_mods:
                    mesh_obj.modifiers.remove(mod)

            # 3. Process weights on the ENTIRE mesh
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            mesh_obj.select_set(True)
            bpy.context.view_layer.objects.active = mesh_obj

            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT') # Select all vertices
            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
            
            bpy.context.object.data.use_paint_mask_vertex = True

            bpy.ops.object.vertex_group_limit_total(limit=1)
            bpy.ops.object.vertex_group_normalize_all(lock_active=False)
            bpy.ops.object.vertex_group_clean(group_select_mode='ALL', limit=0.001)

        print(f"Rigid binding applied to {mesh_obj.name}")
        return {'FINISHED'}

    except Exception as e:
        print(f"Error applying binary weights: {e}")
        return {'CANCELLED'}

    finally:
        # Restore Bone Settings
        for bone, orig_val in restore_deform_settings:
            bone.use_deform = orig_val
            
        # Restore original mode if it was a valid one
        if original_mode in {'EDIT', 'POSE', 'WEIGHT_PAINT', 'OBJECT'}:
            try:
                # Avoid setting mode if context is wrong (e.g. no active object)
                if bpy.context.view_layer.objects.active:
                    bpy.ops.object.mode_set(mode=original_mode)
            except:
                pass

class WYNN_OT_parent_binary_weights(bpy.types.Operator):
    """Parent with Binary (1.0/0.0) Weights"""
    bl_idname = "wynn.parent_binary_weights"
    bl_label = "Parent Binary Weights"
    bl_options = {'REGISTER', 'UNDO'}

    use_selected_bones: bpy.props.BoolProperty(
        name="Selected Bones Only",
        description="Only calculate weights for selected bones",
        default=False
    )

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'OBJECT'

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        mesh_obj = None
        armature = None
        
        active = context.active_object
        selected = context.selected_objects

        if active and active.type == 'ARMATURE':
            armature = active
            for obj in selected:
                if obj.type == 'MESH':
                    mesh_obj = obj
                    break
        elif active and active.type == 'MESH':
            mesh_obj = active
            # Find armature from parent or modifier
            if mesh_obj.parent and mesh_obj.parent.type == 'ARMATURE':
                armature = mesh_obj.parent
            else:
                for mod in mesh_obj.modifiers:
                    if mod.type == 'ARMATURE' and mod.object:
                        armature = mod.object
                        break
                        
        if not mesh_obj or not armature:
            self.report({'ERROR'}, "Selection must include a Mesh and an Armature.")
            return {'CANCELLED'}

        target_bone_names = None
        if self.use_selected_bones:
            # We need to be in pose mode to get selected_pose_bones
            prev_active = context.view_layer.objects.active
            context.view_layer.objects.active = armature
            was_pose = (armature.mode == 'POSE')
            if not was_pose: bpy.ops.object.mode_set(mode='POSE')
            
            target_bone_names = {pb.name for pb in context.selected_pose_bones}
            
            if not was_pose: bpy.ops.object.mode_set(mode='OBJECT')
            context.view_layer.objects.active = prev_active
            
            if not target_bone_names:
                self.report({'WARNING'}, "'Selected Bones Only' is checked, but no bones are selected.")
                return {'CANCELLED'}

        result = apply_binary_weights(mesh_obj, armature, target_bone_names, from_weight_paint=False)
        
        if result == {'HEAT_FAILED'}:
            self.report({'ERROR'}, "Bone Heat Failed: Mesh has holes, overlaps, or bad scale.")
        elif result == {'CANCELLED'}:
            self.report({'ERROR'}, "Script Failed. Check System Console.")
            
        return result

class WYNN_OT_assign_binary_weights(bpy.types.Operator):
    """Assign Binary (1.0/0.0) Weights to selected bones"""
    bl_idname = "wynn.assign_binary_weights"
    bl_label = "Assign Binary Weight to Bone"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.active_object and 
                context.active_object.type == 'MESH' and 
                context.mode == 'PAINT_WEIGHT')

    def execute(self, context):
        mesh_obj = context.active_object
        armature = None
        # Find the armature from the mesh's modifiers
        for mod in mesh_obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object:
                armature = mod.object
                break

        if not armature:
            self.report({'ERROR'}, "No Armature modifier found on the active object.")
            return {'CANCELLED'}

        # In Weight Paint mode, selected pose bones are in context.selected_pose_bones
        target_bone_names = {pb.name for pb in context.selected_pose_bones}

        result = apply_binary_weights(mesh_obj, armature, target_bone_names, from_weight_paint=True)

        if result == {'HEAT_FAILED'}:
            self.report({'ERROR'}, "Bone Heat Failed: Mesh has holes, overlaps, or bad scale.")
        elif result == {'CANCELLED'}:
            self.report({'ERROR'}, "Script Failed. Check System Console.")
            
        return result

def register():
    bpy.utils.register_class(WYNN_OT_parent_binary_weights)
    bpy.utils.register_class(WYNN_OT_assign_binary_weights)

def unregister():
    bpy.utils.unregister_class(WYNN_OT_parent_binary_weights)
    bpy.utils.unregister_class(WYNN_OT_assign_binary_weights)

if __name__ == "__main__":
    register()