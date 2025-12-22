import bpy
from . import binary_weight
from . import pie
from . import Smooth
from . import WeightMode
from . import PaintWeight
from . import WynnWeightBrush

# Define a list of all classes in this module to register
classes_to_register = [
    binary_weight.WYNN_OT_parent_binary_weights,
    binary_weight.WYNN_OT_assign_binary_weights,
    pie.VIEW3D_MT_pie_rig_helpers,
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
    
    # You can also register keymaps or other things here
    print("Registered Rigging submodule")

def unregister():
    """Unregisters all rig-related classes"""
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
        
    WeightMode.unregister()
    PaintWeight.unregister()
    WynnWeightBrush.unregister()
        
    # You can also unregister keymaps or other things here
    print("Unregistered Rigging submodule")