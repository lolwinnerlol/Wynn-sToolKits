import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty, CollectionProperty, PointerProperty

# -------------------------------------------------------------------
#   Data Structures
# -------------------------------------------------------------------

class OnionSkinObjectItem(bpy.types.PropertyGroup):
    """Reference to an object within a group"""
    obj: PointerProperty(type=bpy.types.Object, name="Object")

class OnionSkinGroup(bpy.types.PropertyGroup):
    """A logical group of objects for onion skinning"""
    name: StringProperty(name="Group Name", default="Group")
    is_active: BoolProperty(name="Active", default=True, description="Enable/Disable this group")
    
    objects: CollectionProperty(type=OnionSkinObjectItem)
    active_object_index: IntProperty()

# -------------------------------------------------------------------
#   Operators
# -------------------------------------------------------------------

class WYNN_OT_add_onion_group(bpy.types.Operator):
    """Add a new object group"""
    bl_idname = "wynn.add_onion_group"
    bl_label = "Add Group"
    
    def execute(self, context):
        settings = context.scene.wynn_onion
        group = settings.groups.add()
        group.name = f"Group {len(settings.groups)}"
        settings.active_group_index = len(settings.groups) - 1
        return {'FINISHED'}

class WYNN_OT_remove_onion_group(bpy.types.Operator):
    """Remove the active object group"""
    bl_idname = "wynn.remove_onion_group"
    bl_label = "Remove Group"
    
    @classmethod
    def poll(cls, context):
        return context.scene.wynn_onion.groups
    
    def execute(self, context):
        settings = context.scene.wynn_onion
        settings.groups.remove(settings.active_group_index)
        settings.active_group_index = max(0, min(settings.active_group_index, len(settings.groups) - 1))
        return {'FINISHED'}

class WYNN_OT_add_selected_to_onion_group(bpy.types.Operator):
    """Add selected objects to the active group"""
    bl_idname = "wynn.add_selected_to_onion_group"
    bl_label = "Add Selected"
    
    @classmethod
    def poll(cls, context):
        return context.scene.wynn_onion.groups and context.selected_objects
    
    def execute(self, context):
        settings = context.scene.wynn_onion
        group = settings.groups[settings.active_group_index]
        
        added_count = 0
        current_objs = {item.obj for item in group.objects}
        
        for obj in context.selected_objects:
            if obj not in current_objs:
                item = group.objects.add()
                item.obj = obj
                item.name = obj.name
                added_count += 1
                
        if added_count > 0:
            self.report({'INFO'}, f"Added {added_count} objects to {group.name}")
        else:
            self.report({'WARNING'}, "Selected objects are already in the group")
            
        return {'FINISHED'}

class WYNN_OT_remove_onion_object(bpy.types.Operator):
    """Remove inactive object from the group list"""
    bl_idname = "wynn.remove_onion_object"
    bl_label = "Remove Object"
    
    def execute(self, context):
        settings = context.scene.wynn_onion
        group = settings.groups[settings.active_group_index]
        if group.objects and group.active_object_index < len(group.objects):
            group.objects.remove(group.active_object_index)
        return {'FINISHED'}

class WYNN_OT_select_onion_group_objects(bpy.types.Operator):
    """Select all objects in this group"""
    bl_idname = "wynn.select_onion_group_objects"
    bl_label = "Select Group Objects"
    
    def execute(self, context):
        settings = context.scene.wynn_onion
        group = settings.groups[settings.active_group_index]
        
        for item in group.objects:
            if item.obj:
                item.obj.select_set(True)
        return {'FINISHED'}

# -------------------------------------------------------------------
#   UI Drawing
# -------------------------------------------------------------------

def draw_groups_ui(layout, context):
    settings = context.scene.wynn_onion
    if not settings: return

    # Groups Box
    box = layout.box()
    row = box.row()
    row.label(text="Groups")
    
    if settings.groups:
        row = box.row()
        row.template_list("UI_UL_list", "onion_groups", settings, "groups", settings, "active_group_index", rows=3)
        
        col = row.column(align=True)
        col.operator("wynn.add_onion_group", text="", icon='ADD')
        col.operator("wynn.remove_onion_group", text="", icon='REMOVE')
        
        # Active Group Controls
        if settings.active_group_index < len(settings.groups):
            group = settings.groups[settings.active_group_index]
            
            g_box = box.box()
            # Header with checkbox
            row = g_box.row()
            row.prop(group, "is_active", text="")
            row.prop(group, "name", text="")
            
            # Actions
            row = g_box.row(align=True)
            row.operator("wynn.add_selected_to_onion_group", text="Add Selected", icon='ADD')
            row.operator("wynn.select_onion_group_objects", text="Select All", icon='RESTRICT_SELECT_OFF')
            
            # Objects List
            g_box.label(text="Objects in Group:")
            row = g_box.row()
            row.template_list("UI_UL_list", "onion_objects", group, "objects", group, "active_object_index", rows=4)
            
            col = row.column(align=True)
            col.operator("wynn.remove_onion_object", text="", icon='REMOVE')
            
    else:
        box.operator("wynn.add_onion_group", text="Add New Group", icon='ADD')

# -------------------------------------------------------------------
#   Registration
# -------------------------------------------------------------------

classes = (
    OnionSkinObjectItem,
    OnionSkinGroup,
    WYNN_OT_add_onion_group,
    WYNN_OT_remove_onion_group,
    WYNN_OT_add_selected_to_onion_group,
    WYNN_OT_remove_onion_object,
    WYNN_OT_select_onion_group_objects,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
