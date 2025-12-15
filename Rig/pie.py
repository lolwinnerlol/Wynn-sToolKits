import bpy

class VIEW3D_MT_pie_rig_helpers(bpy.types.Menu):
    """Pie menu for rigging helper tools"""
    bl_idname = "VIEW3D_MT_pie_rig_helpers"
    bl_label = "Rig Helpers"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()
        wynn_props = context.window_manager.wynn_rig_props

        # Left
        pie.operator("wynn.parent_binary_weights", text="Parent Binary Weights", icon='GROUP_BONE')
        
        # Right
        pie.operator("wynn.smooth_weights", text="Smooth Symmetrize", icon='SMOOTHCURVE')
        
        # Bottom
        if wynn_props.weight_mode_on:
            pie.operator("wynn.toggle_weight_mode", text="Deform Bone: ON", icon='HIDE_ON', depress=True)
        else:
            pie.operator("wynn.toggle_weight_mode", text="Deform Bone: OFF", icon='HIDE_OFF', depress=False)
            
        # Top-Right
        is_weight_paint = context.active_object and context.active_object.mode == 'WEIGHT_PAINT'
        if is_weight_paint:
            pie.operator("wynn.setup_weight_paint", text="Exit Paint Mode", icon='OBJECT_DATAMODE', depress=True)
        else:
            pie.operator("wynn.setup_weight_paint", text="Setup Paint Mode", icon='BRUSH_DATA')
