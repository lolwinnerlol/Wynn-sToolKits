import bpy
import os

class WYNN_OT_enable_rig_ui(bpy.types.Operator):
    """Enable Rig UI by loading the associated script for the active armature"""
    bl_idname = "wynn.enable_rig_ui"
    bl_label = "Enable Rig UI"
    bl_description = "Load and execute the rig script for the selected armature from the central resource folder"
    bl_options = {'REGISTER', 'UNDO'}

    # Path to the directory containing rig scripts
    SCRIPT_DIR = r"X:\My Drive\80_Resources\RigScripts"

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.active_object
        
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Selected object is not an Armature")
            return {'CANCELLED'}

        # Construct the expected script path (ignoring .### suffix)
        # e.g. "OhmGirl.001" -> "OhmGirl.py"
        base_name = obj.name.split('.')[0]
        script_name = f"{base_name}.py"
        script_path = os.path.join(self.SCRIPT_DIR, script_name)

        if not os.path.exists(script_path):
            self.report({'ERROR'}, f"Script not found: {script_path}")
            return {'CANCELLED'}

        try:
            # Load and execute the script
            # We use compile + exec to run it in the current context, similar to running a text block in Blender
            with open(script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()
            
            global_namespace = {"__name__": "__main__"}
            exec(compile(script_content, script_path, 'exec'), global_namespace)
            
            self.report({'INFO'}, f"Successfully ran Rig UI script: {script_name}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to execute script: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}
