import bpy
import os
import re

def apply_camera_background(report_func, cam_obj):
    cam_data = cam_obj.data
    cam_data.show_background_images = True
    cam_data.passepartout_alpha = 0.9
    
    image_name = "235Crop.png"
    img = bpy.data.images.get(image_name)
    
    # If not found in blend, try to find in this folder (Extra)
    if not img:
        current_dir = os.path.dirname(__file__)
        image_path = os.path.join(current_dir, image_name)
        
        if os.path.exists(image_path):
            try:
                img = bpy.data.images.load(image_path)
            except: pass
    
    if not img:
        report_func({'WARNING'}, f"Image '{image_name}' not found. Please load it first.")
    
    if len(cam_data.background_images) == 0:
        bg = cam_data.background_images.new()
    else:
        bg = cam_data.background_images[0]
        
    if img:
        bg.image = img
    
    bg.alpha = 1.0
    bg.display_depth = 'FRONT'

class WYNN_OT_set_camera_background(bpy.types.Operator):
    """Set active camera background to 235Crop.png"""
    bl_idname = "wynn.set_camera_background"
    bl_label = "Set Camera Background"
    bl_options = {'REGISTER', 'UNDO'}

    cut_number: bpy.props.IntProperty(name="Cut Number", default=1, min=1)

    @classmethod
    def poll(cls, context):
        return context.selected_objects and any(obj.type == 'CAMERA' for obj in context.selected_objects)

    def invoke(self, context, event):
        cameras = [obj for obj in context.selected_objects if obj.type == 'CAMERA']
        if len(cameras) == 1:
            cam = cameras[0]
            if not re.match(r"^C_\d+$", cam.name):
                return context.window_manager.invoke_props_dialog(self)
        return self.execute(context)

    def execute(self, context):
        cameras = [obj for obj in context.selected_objects if obj.type == 'CAMERA']
        if len(cameras) == 1:
            cam = cameras[0]
            context.scene.camera = cam
            if not re.match(r"^C_\d+$", cam.name):
                cam.name = f"C_{self.cut_number}"
            bpy.ops.view3d.view_camera()

        for cam in cameras:
            apply_camera_background(self.report, cam)
        self.report({'INFO'}, f"Applied background to {len(cameras)} camera(s).")
        return {'FINISHED'}

class WYNN_OT_add_project_camera(bpy.types.Operator):
    """Add a new camera named C_x"""
    bl_idname = "wynn.add_project_camera"
    bl_label = "Add Project Camera"
    bl_options = {'REGISTER', 'UNDO'}

    cut_number: bpy.props.IntProperty(name="Cut Number", default=1, min=1)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        cam_name = f"C_{self.cut_number}"
        cam_data = bpy.data.cameras.new(name=cam_name)
        cam_obj = bpy.data.objects.new(name=cam_name, object_data=cam_data)
        context.collection.objects.link(cam_obj)
        
        bpy.ops.object.select_all(action='DESELECT')
        cam_obj.select_set(True)
        context.view_layer.objects.active = cam_obj
        
        apply_camera_background(self.report, cam_obj)
        bpy.ops.view3d.object_as_camera()
        return {'FINISHED'}

class WYNN_OT_toggle_rule_of_thirds(bpy.types.Operator):
    """Toggle Rule of Thirds for selected cameras"""
    bl_idname = "wynn.toggle_rule_of_thirds"
    bl_label = "Toggle Rule of Thirds"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.selected_objects and any(obj.type == 'CAMERA' for obj in context.selected_objects)

    def execute(self, context):
        cameras = [obj for obj in context.selected_objects if obj.type == 'CAMERA']
        
        # Determine target state based on active camera (toggle)
        target_state = True
        if context.active_object and context.active_object.type == 'CAMERA':
            target_state = not context.active_object.data.show_composition_thirds
        
        for cam in cameras:
            cam.data.show_composition_thirds = target_state
            
        self.report({'INFO'}, f"Rule of Thirds {'Enabled' if target_state else 'Disabled'} for {len(cameras)} camera(s).")
        return {'FINISHED'}

class WYNN_OT_fly_camera(bpy.types.Operator):
    """Start Fly/Walk Navigation"""
    bl_idname = "wynn.fly_camera"
    bl_label = "Fly Navigation"

    @classmethod
    def poll(cls, context):
        return context.space_data and context.space_data.type == 'VIEW_3D'

    def execute(self, context):
        bpy.ops.view3d.navigate('INVOKE_DEFAULT')
        return {'FINISHED'}

def register():
    bpy.utils.register_class(WYNN_OT_set_camera_background)
    bpy.utils.register_class(WYNN_OT_add_project_camera)
    bpy.utils.register_class(WYNN_OT_toggle_rule_of_thirds)
    bpy.utils.register_class(WYNN_OT_fly_camera)

def unregister():
    bpy.utils.unregister_class(WYNN_OT_set_camera_background)
    bpy.utils.unregister_class(WYNN_OT_add_project_camera)
    bpy.utils.unregister_class(WYNN_OT_toggle_rule_of_thirds)
    bpy.utils.unregister_class(WYNN_OT_fly_camera)