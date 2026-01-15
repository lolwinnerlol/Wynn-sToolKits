bl_info = {
    "name": "Wynn's Toolkits",
    "author": "suthiphan khamnong",
    "version": (1, 5, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > Wynn's Toolkits",
    "description": "Collection of tools for projects",
    "warning": "",
    "doc_url": "https://github.com/lolwinnerlol/Wynn-sToolKits",
    "category": "Wynn's Toolkits",
}

import bpy
from bpy.props import BoolProperty
import sys
from . import updater

# Fix: Inject root updater into Animate package to prevent loading stray/empty local updater.py
sys.modules[__name__ + ".Animate.updater"] = updater

from . import Animate, Model, Rig, Extra


# -------------------------------------------------------------------
#   Update Functions
# -------------------------------------------------------------------

def update_overlay_visibility(self, context):
    """Dynamically updates overlay visibility when the checkbox is toggled"""
    # This function is called by the 'toggle_overlays' property update
    # We need to ensure we are in a context where this makes sense
    if context.space_data and context.space_data.type == 'VIEW_3D':
        stored_props = getattr(context.window_manager, "wynn_animator_props", None)
        if not stored_props: return
        
        # Only execute the logic if the silhouette tool is currently active
        if stored_props.is_silhouette_active:
            overlay = context.space_data.overlay
            
            # If the user just checked the box, hide the overlays
            if self.toggle_overlays:
                # We also need to mark that we've taken control of the overlay state
                if not stored_props.overlays_were_toggled:
                    stored_props.show_overlays = overlay.show_overlays
                    stored_props.overlays_were_toggled = True
                overlay.show_overlays = False
            # If the user unchecked the box, restore the original overlay state
            else:
                # Only restore if we were the ones who toggled them
                if stored_props.overlays_were_toggled:
                    overlay.show_overlays = stored_props.show_overlays
                    stored_props.overlays_were_toggled = False


# -------------------------------------------------------------------
#   Addon Preferences & Properties
# -------------------------------------------------------------------

class WynnAnimatorAddonPreferences(bpy.types.AddonPreferences):
    """Defines the preferences for the Wynnimate addon"""
    bl_idname = __name__

    # Existing properties kept for compatibility but hidden from UI
    toggle_overlays: bpy.props.BoolProperty(
        name="Toggle Overlays",
        description="Enable to automatically hide overlays when using the Silhouette Tool",
        default=True,
        update=update_overlay_visibility
    )
    silhouette_color: bpy.props.FloatVectorProperty(
        name="Silhouette Color",
        description="The color of the object Silhouettee",
        subtype='COLOR',
        default=(0.0, 0.0, 0.0), # Default to black
        min=0.0, max=1.0
    )
    background_color: bpy.props.FloatVectorProperty(
        name="Background Color",
        description="The background color when Silhouette is active",
        subtype='COLOR',
        default=(1.0, 1.0, 1.0), # Default to white
        min=0.0, max=1.0
    )

    edit_mode_use_falloff: bpy.props.BoolProperty(
        name="Edit Mode Falloff",
        description="If enabled, 'Use Falloff' will be ON by default when using Edit Mode Weight tools",
        default=False
    )

    # New Role Visibility Properties
    enable_model: bpy.props.BoolProperty(
        name="Model",
        description="Enable Modeling Tools",
        default=True
    )
    enable_animation: bpy.props.BoolProperty(
        name="Animation",
        description="Enable Animation Tools",
        default=True
    )
    enable_rig: bpy.props.BoolProperty(
        name="Rig",
        description="Enable Rigging Tools",
        default=False
    )
    enable_extra: bpy.props.BoolProperty(
        name="Extra",
        description="Enable Extra Tools",
        default=True
    )

    def draw(self, context):
        layout = self.layout
        
        # Only display Role Visibility options
        box = layout.box()
        box.label(text="Role Visibility", icon='HIDE_OFF')
        col = box.column()
        col.prop(self, "enable_model")
        col.prop(self, "enable_animation")
        col.prop(self, "enable_rig")
        col.prop(self, "enable_extra")
       
        # Update buttons hidden but functionality remains if needed 
        # (Removed per "only option of the role visibility" request)


class WA_PG_viewport_storage(bpy.types.PropertyGroup):
    """Stores the user's viewport settings before they are changed."""
    is_silhouette_active: bpy.props.BoolProperty(
        name="Is Silhouette Active",
        description="Tracks if the silhouette mode is currently on",
        default=False
    )
    overlays_were_toggled: bpy.props.BoolProperty(
        name="Internal: Tracks if script toggled overlays",
        description="Used to ensure we only restore overlay state if we changed it",
        default=False
    )
    animation_tools_expanded: bpy.props.BoolProperty(
        name="Animation Tools", 
        default=True
    )
    model_tools_expanded: bpy.props.BoolProperty(
        name="Model Tools",
        default=True
    )
    playblast_expanded: bpy.props.BoolProperty(
        name="Playblast", 
        default=True
    )
    onion_skin_expanded: bpy.props.BoolProperty(
        name="Onion Skin",
        default=False
    )
    show_overlays: bpy.props.BoolProperty(name="Show Overlays")
    light: bpy.props.StringProperty(name="Light")
    color_type: bpy.props.StringProperty(name="Color Type")
    single_color: bpy.props.FloatVectorProperty(name="Single Color", subtype='COLOR', size=3)
    background_type: bpy.props.StringProperty(name="Background Type")
    background_color: bpy.props.FloatVectorProperty(name="Background Color", subtype='COLOR', size=3)
    wireframe_color_type: bpy.props.StringProperty(name="Wireframe Color Type")


class WYNN_PG_rig_props(bpy.types.PropertyGroup):
    """Stores properties for the rigging toolkit."""
    weight_mode_on: bpy.props.BoolProperty(
        name="Weight Mode",
        description="Isolate Deform bone for weight painting",
        default=False
    )
    collection_visibility: bpy.props.StringProperty(
        name="Stored Bone Collection Visibility"
    )

# -------------------------------------------------------------------
#   Parent Panel
# -------------------------------------------------------------------

class WYNN_PT_main_panel(bpy.types.Panel):
    """The main parent panel for all Wynn's Toolkits panels"""
    bl_label = "Wynn's Toolkits"
    bl_idname = "WYNN_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Wynn's Toolkits"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

# -------------------------------------------------------------------
#   Sub Panels (Tabs)
# -------------------------------------------------------------------



class WYNN_PT_model_tab(bpy.types.Panel):
    """Modeling Tools Tab"""
    bl_label = "Model"
    bl_idname = "WYNN_PT_model_tab"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Wynn's Toolkits"
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "WYNN_PT_main_panel"

    @classmethod
    def poll(cls, context):
        prefs = context.preferences.addons[__name__].preferences
        return prefs.enable_model

    def draw(self, context):
        layout = self.layout
        props = getattr(context.window_manager, "wynn_animator_props", None)
        if not props: return

        # Main collapsible box
        main_box = layout.box()
        row = main_box.row()
        row.prop(props, "model_tools_expanded",
                 icon="DOWNARROW_HLT" if props.model_tools_expanded else "RIGHTARROW",
                 text="Vertex Color ID", emboss=False)

        if props.model_tools_expanded:
            # We can't access draw() of another panel class directly like this usually in strict API, 
            # but it often works in Python. Better to use layout.popover or struct if registered.
             # However, since VertexColorIDPanel is registered, it might show on its own if we don't handle it.
             # It acts as a sub-panel? No, VertexColorIDPanel in vertex_color_id.py uses BL_REGION_TYPE='UI'.
             # It will show up in the sidebar. We might want to suppress it if Model is disabled or integrate it here.
             # The existing code calls .draw directly: bpy.types.OBJECT_PT_vertex_color_id.draw(self, context)
             # This injects its UI into this panel.
            if hasattr(bpy.types, "OBJECT_PT_vertex_color_id"):
                bpy.types.OBJECT_PT_vertex_color_id.draw(self, context)

class WYNN_PT_animation_tab(bpy.types.Panel):
    """Animation Tools Tab"""
    bl_label = "Animation"
    bl_idname = "WYNN_PT_animation_tab"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Wynn's Toolkits"
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "WYNN_PT_main_panel"

    @classmethod
    def poll(cls, context):
        prefs = context.preferences.addons[__name__].preferences
        return prefs.enable_animation

    def draw(self, context):
        layout = self.layout
        # Get addon preferences and custom properties
        prefs = context.preferences.addons[__name__].preferences
        props = getattr(context.window_manager, "wynn_animator_props", None)
        if not props: return
        scene = context.scene

        # Main collapsible box
        main_box = layout.box()
        row = main_box.row()
        row.prop(props, "animation_tools_expanded", 
                 icon="DOWNARROW_HLT" if props.animation_tools_expanded else "RIGHTARROW",
                 text="WynnAnimate (SHIFT+V)", emboss=False)

        if props.animation_tools_expanded:
            # Viewport Tools Section
            vp_box = main_box.box()
            vp_box.label(text="Viewport")
            vp_box.operator("wm.silhouette_tool", text="Toggle Silhouette", icon='HIDE_ON')
            vp_box.operator("wynn.open_silhouette_window", text="Silhouette Window", icon='WINDOW')
            
<<<<<<< HEAD
            if hasattr(scene, "wynn_onion"):
                 vp_box.prop(scene.wynn_onion, "use_silhouette_group", text="Silhouette Uses Group")
            
=======
>>>>>>> 82624080c24bb706bc94ecc262d8c766e2ae5f88
            # Rig UI Section
            rig_box = main_box.box()
            rig_box.label(text="Rig UI")
            rig_box.operator("wynn.enable_rig_ui", text="Enable Rig UI", icon='FILE_SCRIPT')

            
            # --- Camera Viewer Settings ---
            from .Animate.silhouette_window import draw_camera_viewer_ui
            draw_camera_viewer_ui(vp_box, context)
            
            # Since these are hidden in prefs, we might want to expose them here?
            # Existing code exposed them here:
            vp_box.prop(prefs, "toggle_overlays")
            
            # Color Settings
            col = vp_box.column(align=True)
            col.prop(prefs, "silhouette_color", text="Object Color")
            col.prop(prefs, "background_color", text="BG Color")

            # Motion Paths Section
            mp_box = main_box.box()
            mp_box.label(text="Motion Paths")
            row = mp_box.row(align=True)
            row.operator("wm.calculate_motion_path", text="Calculate", icon='ACTION_TWEAK')
            row.operator("wm.update_motion_path", text="Update", icon='FILE_REFRESH')
            mp_box.operator("wm.clear_motion_path", text="Clear All Paths", icon='X')
        
        # Onion Skin Section
        os_box = layout.box()
        row = os_box.row()
        row.prop(props, "onion_skin_expanded", 
                 icon="DOWNARROW_HLT" if props.onion_skin_expanded else "RIGHTARROW",
                 text="Onion Skinning", emboss=False)
        
        if props.onion_skin_expanded:
            from .Animate.onion_skin import draw_onion_skin_ui
            draw_onion_skin_ui(os_box, context)

        # Playblast Section
        pb_box = layout.box()
        row = pb_box.row()
        row.prop(props, "playblast_expanded", 
                 icon="DOWNARROW_HLT" if props.playblast_expanded else "RIGHTARROW",
                 text="Playblast", emboss=False)

        if props.playblast_expanded:
            col = pb_box.column()
            col.prop(scene, "playblast_process", text="Process")
            if scene.playblast_process == 'OTHERS':
                col.prop(scene, "playblast_process_custom", text="Custom")
            col.prop(scene, "playblast_version", text="Version")
            col.prop(scene, "playblast_note", text="Animator ")
            col.operator("anim.playblast", text="Render Playblast", icon='RENDER_ANIMATION')


class WYNN_PT_rig_tab(bpy.types.Panel):
    """Rigging Tools Tab"""
    bl_label = "Rig"
    bl_idname = "WYNN_PT_rig_tab"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Wynn's Toolkits"
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "WYNN_PT_main_panel"

    @classmethod
    def poll(cls, context):
        prefs = context.preferences.addons[__name__].preferences
        return prefs.enable_rig

    def draw(self, context):
        layout = self.layout
        wynn_props = getattr(context.window_manager, "wynn_rig_props", None)
        
        # Object / Weight Paint / Pose Mode Tools
        if context.mode != 'EDIT_MESH':
            layout.label(text="Weight Tools")
            
            # Paint Mode Toggle
            is_weight_paint = context.mode == 'PAINT_WEIGHT'
            
            if is_weight_paint:
                layout.operator("wynn.smear_perf_monitor", text="WynnWeightBrush", icon='BRUSH_DATA')
                layout.separator()
                layout.operator("wynn.setup_weight_paint", text="Exit Paint Mode", icon='OBJECT_DATAMODE', depress=True)
            else:
                layout.operator("wynn.setup_weight_paint", text="Setup Paint Mode", icon='BRUSH_DATA')

            # Deform Bone Toggle
            if wynn_props and wynn_props.weight_mode_on:
                layout.operator("wynn.toggle_weight_mode", text="Deform Bone: ON", icon='HIDE_ON', depress=True)
            else:
                layout.operator("wynn.toggle_weight_mode", text="Deform Bone: OFF", icon='HIDE_OFF', depress=False)

            layout.separator()
            layout.operator("wynn.parent_binary_weights", text="Parent Binary Weights", icon='GROUP_BONE')

        # Edit Mode Tools
        else:
            layout.label(text="Edit Tools")
            col = layout.column(align=True)
            col.operator("wynn.edit_harden_weights", text="Harden Weight", icon='DRIVER')
            col.operator("wynn.edit_smooth_weights", text="Smooth Weight", icon='SMOOTHCURVE')

class WYNN_PT_extra_tab(bpy.types.Panel):
    """Extra Tools Tab"""
    bl_label = "Extra"
    bl_idname = "WYNN_PT_extra_tab"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Wynn's Toolkits"
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "WYNN_PT_main_panel"

    @classmethod
    def poll(cls, context):
        prefs = context.preferences.addons[__name__].preferences
        return prefs.enable_extra

    def draw(self, context):
        layout = self.layout
        
        box = layout.box()
        box.label(text="Camera Tools")
        
        if context.scene.camera:
            box.label(text=f"Active: {context.scene.camera.name}", icon='CAMERA_DATA')
            
        box.operator("wynn.set_camera_background", text="Set Project Cam.", icon='TRIA_DOWN_BAR')
        box.operator("wynn.add_project_camera", text="Add Project Cam.", icon='ADD')
        
        row = box.row(align=True)
        row.operator("wynn.toggle_rule_of_thirds", text="CamGuide", icon='MESH_GRID')
        row.operator("wynn.fly_camera", text="Pilot Cam", icon='VIEW_PAN')
        
        if context.active_object and context.active_object.type == 'CAMERA':
            box.separator()
            box.prop(context.active_object.data, "lens", text="Focal Length")
        
        # Change the URL below to your actual documentation link
        layout.operator("wm.url_open", text="GitHub & Documentation", icon='HELP').url = "https://github.com/lolwinnerlol/Wynn-sToolKits"


# -------------------------------------------------------------------
#   Registration
# -------------------------------------------------------------------

# Create a list of all classes to register
# To add a new panel, create the class and add it to this list
classes_to_register = [
    WYNN_PT_main_panel,
    WYNN_PT_model_tab,
    WYNN_PT_animation_tab,
    WYNN_PT_rig_tab,
    WYNN_PT_extra_tab,
    WynnAnimatorAddonPreferences,
    WA_PG_viewport_storage,
    WYNN_PG_rig_props,
    updater.WM_OT_check_for_updates,
    updater.WM_OT_update_addon,
]

addon_keymaps = []

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)
    
    # Register the submodule
    Animate.register()
    Model.register()
    Rig.register()
    Extra.register()

    # Attach the property group to the WindowManager
    bpy.types.WindowManager.wynn_animator_props = bpy.props.PointerProperty(
        type=WA_PG_viewport_storage
    )
    bpy.types.WindowManager.wynn_rig_props = bpy.props.PointerProperty(
        type=WYNN_PG_rig_props
    )
    bpy.types.WindowManager.wynn_update_available = BoolProperty(default=False)
    
    # Register Keymaps
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new('wm.call_menu_pie', 'V', 'PRESS')
        kmi.properties.name = Rig.pie.VIEW3D_MT_custom_pie_menu.bl_idname
        addon_keymaps.append((km, kmi))

    # Auto-check for updates on startup (delayed)
    def auto_check_update():
        is_avail, _, _ = updater.check_updates_core()
        for wm_instance in bpy.data.window_managers:
            wm_instance.wynn_update_available = is_avail
    bpy.app.timers.register(auto_check_update, first_interval=2.0)
    
    print(r"""
 _       __                 _          ______            ______                ___  ______   ____       __       
| |     / /_  ______  ____ ( )_____   /_  __/___  ____  / / __ )____  _  __   <  / / ____/  / __ )___  / /_____ _
| | /| / / / / / __ \/ __ \|// ___/    / / / __ \/ __ \/ / __  / __ \| |/_/   / / /___ \   / __  / _ \/ __/ __ `/
| |/ |/ / /_/ / / / / / / / (__  )    / / / /_/ / /_/ / / /_/ / /_/ />  <    / / ____/ /  / /_/ /  __/ /_/ /_/ / 
|__/|__/\__, /_/ /_/_/ /_/ /____/    /_/  \____/\____/_/_____/\____/_/|_|   /_(_)_____/  /_____/\___/\__/\__,_/  
       /____/                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     
    """)


def unregister():
    # Unregister Keymaps
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    # Unregister the submodule first
    Animate.unregister()
    Model.unregister()
    Rig.unregister()
    Extra.unregister()

    # Delete the custom property from the WindowManager
    del bpy.types.WindowManager.wynn_animator_props
    del bpy.types.WindowManager.wynn_rig_props
    del bpy.types.WindowManager.wynn_update_available

    # Unregister in reverse order to avoid errors
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
