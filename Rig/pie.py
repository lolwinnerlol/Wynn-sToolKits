import bpy

class WYNN_MT_edit_weights(bpy.types.Menu):
    bl_label = "Edit Weights"
    bl_idname = "WYNN_MT_edit_weights"

    def draw(self, context):
        layout = self.layout
        is_weight_paint = context.mode == 'PAINT_WEIGHT'
        
        if is_weight_paint:
            layout.operator("wynn.assign_binary_weights", text="Assign Binary Weight", icon='GROUP_BONE')
        else:
            layout.operator("wynn.parent_binary_weights", text="Parent Binary Weights", icon='GROUP_BONE')
        layout.operator("wynn.smooth_weights", text="Smooth Symmetrize", icon='SMOOTHCURVE')

class VIEW3D_MT_pie_rig_helpers(bpy.types.Menu):
    """Pie menu for rigging helper tools"""
    bl_idname = "VIEW3D_MT_pie_rig_helpers"
    bl_label = "Wynn's Weight Tools"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()
        wynn_props = getattr(context.window_manager, "wynn_rig_props", None)
        is_weight_paint = context.mode == 'PAINT_WEIGHT'

        # Left
        pie.operator("wynn.smear_perf_monitor", text="WynnWeightBrush", icon='BRUSH_DATA')

        # Right
        pie.menu("WYNN_MT_edit_weights", text="EditWeights", icon='MODIFIER')
        
        # Bottom
        if wynn_props and wynn_props.weight_mode_on:
            pie.operator("wynn.toggle_weight_mode", text="Deform Bone: ON", icon='HIDE_ON', depress=True)
        else:
            pie.operator("wynn.toggle_weight_mode", text="Deform Bone: OFF", icon='HIDE_OFF', depress=False)
            
        # Top
        if is_weight_paint:
            pie.operator("wynn.setup_weight_paint", text="Exit Paint Mode", icon='OBJECT_DATAMODE', depress=True)
        else:
            pie.operator("wynn.setup_weight_paint", text="Setup Paint Mode", icon='BRUSH_DATA')
