import bpy
from bpy.props import StringProperty, EnumProperty

from . import silhouette
from . import motion_path
from . import ui
from . import playblast

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
)

def register():
    # Register all the classes (Operators, Menus, etc.)
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.playblast_note = StringProperty(
        name="Note",
        description="Note to be included in the playblast metadata",
        default="Name here"
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

    del bpy.types.Scene.playblast_note
    del bpy.types.Scene.playblast_process
    del bpy.types.Scene.playblast_process_custom
    del bpy.types.Scene.playblast_version

    # Unregister all classes in reverse order to avoid dependency issues
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
