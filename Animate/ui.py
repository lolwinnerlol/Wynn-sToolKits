import bpy
from . import silhouette
from . import motion_path
from . import updater

# Define the Pie Menu
class VIEW3D_MT_pie_animation_helpers(bpy.types.Menu):
    """Pie menu for animation helper tools"""
    bl_idname = "VIEW3D_MT_pie_animation_helpers"
    bl_label = "Animation Helpers"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()
        
        # Left Slot
        pie.operator(silhouette.WM_OT_silhouette_tool.bl_idname, text="Toggle Silhouette", icon='HIDE_ON')
        # Right Slot
        pie.operator(motion_path.WM_OT_calculate_motion_path.bl_idname, text="Calculate Path", icon='ACTION_TWEAK')
        # Bottom Slot
        pie.operator(motion_path.WM_OT_clear_motion_path.bl_idname, text="Clear All Paths", icon='X')
        # Top Slot
        pie.operator(motion_path.WM_OT_update_motion_path.bl_idname, text="Update Path", icon='FILE_REFRESH')
        
        # Top-Right Slot (Only visible if update is available)
        if context.window_manager.wynn_update_available:
            pie.operator(updater.WM_OT_update_addon.bl_idname, text="Update Available!", icon='URL')
