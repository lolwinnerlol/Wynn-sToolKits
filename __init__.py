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
import json
import os
import subprocess
from bpy.props import BoolProperty, StringProperty, EnumProperty
from . import Animate, Model, Rig, Extra

# -------------------------------------------------------------------
#   Helper Functions
# -------------------------------------------------------------------

def get_config_path():
    """Returns the absolute path to the config.json file."""
    return os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    """Loads settings from config.json. Returns None if file doesn't exist."""
    path = get_config_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Wynn's Toolkits: Failed to load config: {e}")
        return None

def save_config(data):
    """Saves settings to config.json."""
    path = get_config_path()
    try:
        with open(path, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Wynn's Toolkits: Configuration saved to {path}")
    except Exception as e:
        print(f"Wynn's Toolkits: Failed to save config: {e}")

def get_addon_preferences(context):
    """Safely retrieves addon preferences, handling folder name discrepancies."""
    # Try the standard __name__ (folder name)
    if __name__ in context.preferences.addons:
        return context.preferences.addons[__name__].preferences
    
    # Try replacing hyphens with underscores (Blender sanitization)
    name_sanitized = __name__.replace("-", "_")
    if name_sanitized in context.preferences.addons:
        return context.preferences.addons[name_sanitized].preferences
        
    return None

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
    
    # Setup Wizard Properties
    user_name: bpy.props.StringProperty(
        name="User Name",
        description="Your name for personalized greetings/metadata",
        default="GothGirl"
    )
    setup_complete: bpy.props.BoolProperty(
        name="Setup Complete",
        description="Has the user ran the first-time setup?",
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
    viewport_expanded: bpy.props.BoolProperty(
        name="Silhouette",
        default=True
    )
    groups_expanded: bpy.props.BoolProperty(
        name="Groups",
        default=True
    )
    motion_paths_expanded: bpy.props.BoolProperty(
        name="Motion Paths",
        default=True
    )
    rig_ui_expanded: bpy.props.BoolProperty(
        name="Import Rig UI",
        default=True
    )
    main_animation_tools_expanded: bpy.props.BoolProperty(
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

class WYNN_OT_setup_wizard(bpy.types.Operator):
    """First Run Setup Wizard"""
    bl_idname = "wynn.setup_wizard"
    bl_label = "Welcome to Wynn's Toolkits"
    bl_options = {'REGISTER', 'INTERNAL'}

    user_name: bpy.props.StringProperty(name="Enter Your Name", default="Animator")
    
    # We will use the addon preferences directly for roles, but let's mirror them here 
    # to show in the dialog or just show the prefs prop in draw.
    # Actually, simpler to just access prefs in draw.

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        prefs = get_addon_preferences(context)
        
        layout.label(text="ยินดีต้อนรับบ! เรามาเริ่มต้นกันดีกว่า", icon='INFO')
        layout.separator()
        
        layout.prop(self, "user_name")
        layout.separator()
        
        layout.label(text="ต้องการเครื่องมืออะไรบ้าง?", icon='PREFERENCES')
        box = layout.box()
        box.prop(prefs, "enable_model", text="Modeling Tools")
        box.prop(prefs, "enable_animation", text="Animation Tools")
        box.prop(prefs, "enable_rig", text="Rigging Tools")
        box.prop(prefs, "enable_extra", text="Extra Tools")

    def execute(self, context):
        prefs = get_addon_preferences(context)
        prefs.user_name = self.user_name
        prefs.setup_complete = True
        
        # Save to JSON
        config_data = {
            "user_name": self.user_name,
            "setup_complete": True,
            "roles": {
                "enable_model": prefs.enable_model,
                "enable_animation": prefs.enable_animation,
                "enable_rig": prefs.enable_rig,
                "enable_extra": prefs.enable_extra
            }
        }
        save_config(config_data)
        
        # Save Blender preferences as well just in case
        bpy.ops.wm.save_userpref()
        
        self.report({'INFO'}, f"Welcome, {self.user_name}! Setup Complete.")
        return {'FINISHED'}

        self.report({'INFO'}, f"Welcome, {self.user_name}! Setup Complete.")
        return {'FINISHED'}


class WYNN_OT_open_playblast_folder(bpy.types.Operator):
    """Open the playblast output folder in Explorer"""
    bl_idname = "wynn.open_playblast_folder"
    bl_label = "Open Folder"
    
    def execute(self, context):
        path = context.scene.playblast_output_path
        # Default to //Playblast/ if empty, allow relative paths
        if not path:
            path = "//Playblast/"
        
        abs_path = bpy.path.abspath(path)
        
        if not os.path.exists(abs_path):
            try:
                os.makedirs(abs_path)
            except Exception as e:
                self.report({'ERROR'}, f"Could not create folder: {str(e)}")
                return {'CANCELLED'}
                
        # Windows specific
        try:
            os.startfile(abs_path)
        except Exception as e:
            self.report({'ERROR'}, f"Could not open folder: {str(e)}")
            return {'CANCELLED'}
            
        return {'FINISHED'}

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
        prefs = get_addon_preferences(context)
        
        if not prefs:
            layout.label(text="Error loading preferences")
            return

        if not prefs.setup_complete:
            layout.label(text="Welcome to Wynn's Toolkits!", icon='COMMUNITY')
            layout.label(text="Please verify your settings.")
            layout.separator()
            layout.operator("wynn.setup_wizard", text="Start Setup", icon='PLAY')
            return
            
        # Normal UI continues here if setup is complete
        row = layout.row()
        row.label(text=f"สวัสดีจ้า, {prefs.user_name}!", icon='USER')
        row.operator("wynn.setup_wizard", text="", icon='PREFERENCES').user_name = prefs.user_name

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
        prefs = get_addon_preferences(context)
        return prefs and prefs.enable_model

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
        prefs = get_addon_preferences(context)
        return prefs and prefs.enable_animation

    def draw(self, context):
        layout = self.layout
        # Get addon preferences and custom properties
        prefs = get_addon_preferences(context)
        props = getattr(context.window_manager, "wynn_animator_props", None)
        if not props: return
        scene = context.scene

        # Main collapsible box
        main_box = layout.box()
        row = main_box.row()
        row.prop(props, "main_animation_tools_expanded", 
                 icon="DOWNARROW_HLT" if props.main_animation_tools_expanded else "RIGHTARROW",
                 text="WynnAnimate (SHIFT+V)", emboss=False)

        if props.main_animation_tools_expanded:
            # Viewport Tools Section (Collapsable)
            vp_box = main_box.box()
            row = vp_box.row()
            row.prop(props, "viewport_expanded", 
                     icon="DOWNARROW_HLT" if props.viewport_expanded else "RIGHTARROW",
                     text="Silhouette", emboss=False)
            
            if props.viewport_expanded:
                vp_box.operator("wm.silhouette_tool", text="Toggle Silhouette", icon='HIDE_ON')

                
                # --- Camera Viewer Settings ---

                
                # Color Settings (Same Row)
                col_row = vp_box.row(align=True)
                col_row.prop(prefs, "silhouette_color", text="")
                col_row.prop(prefs, "background_color", text="")
                
                # Silhouette Uses Group (Under Color)
                if hasattr(scene, "wynn_onion"):
                     vp_box.prop(scene.wynn_onion, "use_silhouette_group", text="Silhouette Uses Group")

            # Groups Section (Collapsable)
            groups_box = main_box.box()
            row = groups_box.row()
            row.prop(props, "groups_expanded", 
                     icon="DOWNARROW_HLT" if props.groups_expanded else "RIGHTARROW",
                     text="Groups", emboss=False)
            
            if props.groups_expanded:
                from .Animate.groups import draw_groups_ui
                draw_groups_ui(groups_box, context)

            # Motion Paths Section (Collapsable)
            mp_box = main_box.box()
            row = mp_box.row()
            row.prop(props, "motion_paths_expanded", 
                     icon="DOWNARROW_HLT" if props.motion_paths_expanded else "RIGHTARROW",
                     text="Motion Paths", emboss=False)
            
            if props.motion_paths_expanded:
                row = mp_box.row(align=True)
                row.operator("wm.calculate_motion_path", text="Calculate", icon='ACTION_TWEAK')
                row.operator("wm.update_motion_path", text="Update", icon='FILE_REFRESH')
                mp_box.operator("wm.clear_motion_path", text="Clear All Paths", icon='X')

            # Rig UI Section (Collapsable)
            rig_box = main_box.box()
            row = rig_box.row()
            row.prop(props, "rig_ui_expanded", 
                     icon="DOWNARROW_HLT" if props.rig_ui_expanded else "RIGHTARROW",
                     text="Import Rig UI", emboss=False)
            
            if props.rig_ui_expanded:
                rig_box.operator("wynn.enable_rig_ui", text="Enable Rig UI", icon='FILE_SCRIPT')
                rig_box.operator("wynn.import_rig", text="Import Rig", icon='IMPORT')
        
            # Onion Skin Section
            os_box = main_box.box()
            row = os_box.row()
            row.prop(props, "onion_skin_expanded", 
                     icon="DOWNARROW_HLT" if props.onion_skin_expanded else "RIGHTARROW",
                     text="Onion Skin", emboss=False)
            
            if props.onion_skin_expanded:
                from .Animate.onion_skin import draw_onion_skin_ui
                draw_onion_skin_ui(os_box, context)

        # Playblast Section
        pb_box = layout.box()
        row = pb_box.row()
        if props.playblast_expanded:
            col = pb_box.column()
            
            # Path Selection
            row = col.row(align=True)
            row.prop(scene, "playblast_output_path", text="")
            row.operator("wynn.open_playblast_folder", text="", icon='EXTERNAL_DRIVE')
            
            col.separator()
            
            col.prop(scene, "playblast_process", text="Process")
            if scene.playblast_process == 'OTHERS':
                col.prop(scene, "playblast_process_custom", text="Custom")
            col.prop(scene, "playblast_version", text="Version")
            col.prop(scene, "playblast_note", text="Note")
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
        prefs = get_addon_preferences(context)
        return prefs and prefs.enable_rig

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
        prefs = get_addon_preferences(context)
        return prefs and prefs.enable_extra

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
    WYNN_OT_setup_wizard,
    WYNN_OT_open_playblast_folder,
    WA_PG_viewport_storage,
    WYNN_PG_rig_props,

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

    
    # Register Keymaps
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new('wm.call_menu_pie', 'V', 'PRESS')
        kmi.properties.name = Rig.pie.VIEW3D_MT_custom_pie_menu.bl_idname
        addon_keymaps.append((km, kmi))

    # Load Config from JSON if it exists
    config = load_config()
    if config:
        # We need to access preferences. Since we just registered, standard method should work
        # but context might not be fully ready in some startup cases.
        # However, accessing addon_preferences via bpy.context.preferences usually works here.
        # Attempt to get prefs
        pass
        # Note: Accessing preferences during register can be tricky if the addon name isn't fully established.
        # But we can try finding it.
        addon_name = __name__
        prefs = None
        if addon_name in bpy.context.preferences.addons:
            prefs = bpy.context.preferences.addons[addon_name].preferences
        
        if prefs:
            prefs.user_name = config.get("user_name", "Animator")
            prefs.setup_complete = config.get("setup_complete", False)
            roles = config.get("roles", {})
            prefs.enable_model = roles.get("enable_model", True)
            prefs.enable_animation = roles.get("enable_animation", True)
            prefs.enable_rig = roles.get("enable_rig", False)
            prefs.enable_extra = roles.get("enable_extra", True)
            print("Wynn's Toolkits: Config loaded.")


    
    print(r"""
 _       __                 _          ______            ____ __ _ __          ___  ______
| |     / /_  ______  ____ ( )_____   /_  __/___  ____  / / //_/(_) /______   <  / / ____/
| | /| / / / / / __ \/ __ \|// ___/    / / / __ \/ __ \/ / ,<  / / __/ ___/   / / /___ \  
| |/ |/ / /_/ / / / / / / / (__  )    / / / /_/ / /_/ / / /| |/ / /_(__  )   / / ____/ /  
|__/|__/\__, /_/ /_/_/ /_/ /____/    /_/  \____/\____/_/_/ |_/_/\__/____/   /_(_)_____/   
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


    # Unregister in reverse order to avoid errors
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
