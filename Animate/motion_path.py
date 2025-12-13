import bpy

# --- Motion Path Operators ---

class WM_OT_calculate_motion_path(bpy.types.Operator):
    """Calculates motion paths for selected bones or objects"""
    bl_idname = "wm.calculate_motion_path"
    bl_label = "Calculate Motion Path"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode == 'POSE':
            if not context.selected_pose_bones:
                self.report({'WARNING'}, "Please select at least one bone.")
                return {'CANCELLED'}
            try:
                bpy.ops.pose.paths_calculate(display_type='RANGE', range='SCENE', bake_location='HEADS')
                self.report({'INFO'}, "Motion paths calculated for selected bones.")
                return {'FINISHED'}
            except Exception as e:
                self.report({'ERROR'}, f"Failed to calculate motion paths: {e}")
                return {'CANCELLED'}
        
        elif context.mode == 'OBJECT':
            if not context.selected_objects:
                self.report({'WARNING'}, "Please select at least one object.")
                return {'CANCELLED'}
            try:
                bpy.ops.object.paths_calculate(display_type='RANGE', range='SCENE')
                self.report({'INFO'}, "Motion paths calculated for selected objects.")
                return {'FINISHED'}
            except Exception as e:
                self.report({'ERROR'}, f"Failed to calculate motion paths: {e}")
                return {'CANCELLED'}
        
        else:
            self.report({'WARNING'}, "Motion Tool requires Object or Pose Mode.")
            return {'CANCELLED'}

class WM_OT_clear_motion_path(bpy.types.Operator):
    """Clears all motion paths for selected objects or active armature"""
    bl_idname = "wm.clear_motion_path"
    bl_label = "Clear All Motion Paths"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode == 'POSE':
            # Check if there is an active armature and if any of its bones have a motion path
            if not context.object or context.object.type != 'ARMATURE':
                self.report({'INFO'}, "No active armature selected.")
                return {'FINISHED'}

            has_any_path = any(pbone.motion_path for pbone in context.object.pose.bones)
            if not has_any_path:
                self.report({'INFO'}, "No motion paths to clear on the active armature.")
                return {'FINISHED'}

            try:
                bpy.ops.pose.paths_clear()
                self.report({'INFO'}, "All motion paths cleared.")
                return {'FINISHED'}
            except Exception as e:
                self.report({'ERROR'}, f"Failed to clear motion paths: {e}")
                return {'CANCELLED'}

        elif context.mode == 'OBJECT':
            if not context.selected_objects:
                self.report({'INFO'}, "No objects selected.")
                return {'FINISHED'}
            
            has_any_path = any(obj.motion_path for obj in context.selected_objects)
            if not has_any_path:
                self.report({'INFO'}, "No motion paths to clear on selected objects.")
                return {'FINISHED'}

            try:
                bpy.ops.object.paths_clear()
                self.report({'INFO'}, "Selected object motion paths cleared.")
                return {'FINISHED'}
            except Exception as e:
                self.report({'ERROR'}, f"Failed to clear motion paths: {e}")
                return {'CANCELLED'}
        
        else:
            self.report({'WARNING'}, "Please switch to Object or Pose Mode.")
            return {'CANCELLED'}

class WM_OT_update_motion_path(bpy.types.Operator):
    """Updates all existing motion paths for the active armature or selected objects"""
    bl_idname = "wm.update_motion_path"
    bl_label = "Update All Motion Paths"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode == 'POSE':
            # Check if there is an active armature and if any of its bones have a motion path
            if not context.object or context.object.type != 'ARMATURE':
                self.report({'INFO'}, "No active armature selected.")
                return {'FINISHED'}

            has_any_path = any(pbone.motion_path for pbone in context.object.pose.bones)
            if not has_any_path:
                self.report({'INFO'}, "No motion paths to update on the active armature.")
                return {'FINISHED'}

            try:
                bpy.ops.pose.paths_update()
                self.report({'INFO'}, "All motion paths updated.")
                return {'FINISHED'}
            except Exception as e:
                self.report({'ERROR'}, f"Failed to update motion paths: {e}")
                return {'CANCELLED'}

        elif context.mode == 'OBJECT':
            if not context.selected_objects:
                self.report({'INFO'}, "No objects selected.")
                return {'FINISHED'}

            has_any_path = any(obj.motion_path for obj in context.selected_objects)
            if not has_any_path:
                self.report({'INFO'}, "No motion paths to update on selected objects.")
                return {'FINISHED'}

            try:
                bpy.ops.object.paths_update()
                self.report({'INFO'}, "Selected object motion paths updated.")
                return {'FINISHED'}
            except Exception as e:
                self.report({'ERROR'}, f"Failed to update motion paths: {e}")
                return {'CANCELLED'}
        
        else:
            self.report({'WARNING'}, "Please switch to Object or Pose Mode.")
            return {'CANCELLED'}
