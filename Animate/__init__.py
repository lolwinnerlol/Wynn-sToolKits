import bpy
from bpy.props import StringProperty, EnumProperty

from . import silhouette

from . import motion_path
from . import ui
from . import playblast
from . import onion_skin
from . import groups
from . import rig_ui
from . import import_rig

# --- Addon Registration ---

# A list to store keymap items for easy registration and unregistration
addon_keymaps = []

# List of all classes that need to be registered with Blender
classes = (
    silhouette.WM_OT_silhouette_tool,
    motion_path.WM_OT_calculate_motion_path,
    motion_path.WM_OT_clear_motion_path,
    motion_path.WM_OT_update_motion_path,
    ui.VIEW3D_MT_pie_animation_helpers,
    playblast.ANIM_OT_playblast,
    playblast.ANIM_OT_edit_playblast_note,
    playblast.ANIM_OT_auto_version,
    rig_ui.WYNN_OT_enable_rig_ui,
)

def register():
    # Register submodule first
    # Register submodule first

    groups.register()
    onion_skin.register()
    import_rig.register()
    
    # Register all the classes (Operators, Menus, etc.)
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.playblast_note = StringProperty(
        name="Note",
        description="Note to be included in the playblast metadata",
        default="Note here"
    )
    bpy.types.Scene.playblast_process = EnumProperty(
        name="Process",
        description="Animation Process Stage",
        items=[
            ('LAYOUT', "Layout", ""),
            ('BLOCKING', "Blocking", ""),
            ('SPLINING', "Splining", ""),
            ('FINAL', "Final", ""),
            ('OTHERS', "Others", ""),
        ],
        default='BLOCKING'
    )
    bpy.types.Scene.playblast_process_custom = StringProperty(
        name="Custom Process",
        default="WIP"
    )
    bpy.types.Scene.playblast_version = StringProperty(
        name="Version",
        description="Version number",
        default="01"
    )
    bpy.types.Scene.playblast_output_path = StringProperty(
        name="Output Path",
        description="Directory to save playblasts",
        default=r"X:\My Drive\50_Render_Output\00_Blender\Playblast\\",
        subtype='DIR_PATH'
    )

    # --- Keymap Registration ---
    # This creates the Shift+V shortcut
    wm = bpy.context.window_manager
    # Create a new keymap for the 3D View space
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        # Add the keymap item that calls our pie menu
        kmi = km.keymap_items.new('wm.call_menu_pie', 'V', 'PRESS', shift=True)
        kmi.properties.name = ui.VIEW3D_MT_pie_animation_helpers.bl_idname
        addon_keymaps.append((km, kmi))

def unregister():
    # --- Keymap Unregistration ---
    # Remove the shortcut when the addon is disabled
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    for prop in ("playblast_note", "playblast_process", "playblast_process_custom", "playblast_version", "playblast_output_path"):
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)

    # Unregister local classes
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
        
    # Unregister submodule
    # Unregister submodule
    onion_skin.unregister()
    groups.unregister()
    import_rig.unregister()

