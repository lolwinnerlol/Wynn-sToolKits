import bpy
from . import binary_weight
from . import pie
from . import Smooth
from . import WeightMode
from . import PaintWeight
from . import WynnWeightBrush
from . import EditModeWeight


# Define a list of all classes in this module to register
classes_to_register = [
    binary_weight.WYNN_OT_parent_binary_weights,
    binary_weight.WYNN_OT_assign_binary_weights,
    pie.VIEW3D_MT_custom_pie_menu,
    pie.WYNN_MT_edit_weights,
    Smooth.WYNN_OT_smooth_weights,
]

def register():
    """Registers all rig-related classes"""
    for cls in classes_to_register:
        bpy.utils.register_class(cls)
    
    WeightMode.register()
    PaintWeight.register()
    WynnWeightBrush.register()
    EditModeWeight.register()

    
    # You can also register keymaps or other things here
    # Keymap Registration
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='Mesh', space_type='EMPTY')
        kmi = km.keymap_items.new('wm.call_menu', 'V', 'PRESS', ctrl=True, shift=True)
        kmi.properties.name = "WYNN_MT_edit_weights"
        addon_keymaps.append((km, kmi))

    print("Registered Rigging submodule")

addon_keymaps = []

def unregister():
    """Unregisters all rig-related classes"""
    # Keymap Unregistration
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
        
    WeightMode.unregister()
    PaintWeight.unregister()
    WynnWeightBrush.unregister()
    EditModeWeight.unregister()

        
    print("Unregistered Rigging submodule")