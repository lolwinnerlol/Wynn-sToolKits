import bpy
import bmesh
import json
import os
from bpy.app.handlers import persistent

PRESET_FILE_NAME = "vertex_color_presets.json"
DEFAULT_PRESET_NAME = "Default"

COLORS_DICT_DEFAULT = {
    "Red": (1, 0, 0),
    "Green": (0, 1, 0),
    "Blue": (0, 0, 1),
    "Yellow": (1, 1, 0),
    "Cyan": (0, 1, 1),
}

# Cache to store loaded presets
CACHE = {"presets": None}

def get_json_path():
    return os.path.join(os.path.dirname(__file__), PRESET_FILE_NAME)

def load_presets():
    path = get_json_path()
    data = {}
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Wynn Toolkits: Error loading presets from {path}: {e}")
    
    # Ensure Default always exists and verify it has content if missing
    if DEFAULT_PRESET_NAME not in data:
        data[DEFAULT_PRESET_NAME] = COLORS_DICT_DEFAULT.copy()
    
    CACHE["presets"] = data
    return data

def save_presets(data):
    path = get_json_path()
    try:
        with open(path, 'w') as f:
            json.dump(data, f, indent=4)
        CACHE["presets"] = data
    except Exception as e:
        print(f"Wynn Toolkits: Error saving presets to {path}: {e}")

def populate_colors(scene, preset_name):
    if CACHE["presets"] is None:
        load_presets()
    
    data = CACHE["presets"].get(preset_name)
    
    # Fallback if somehow empty or missing (e.g. invalid enum value)
    if not data:
        if preset_name == DEFAULT_PRESET_NAME:
            data = COLORS_DICT_DEFAULT
        else:
            return # Should not happen

    scene.wynn_vertex_colors.clear()
    for name, col in data.items():
        item = scene.wynn_vertex_colors.add()
        item.name = name
        item.color = col

def update_preset(self, context):
    populate_colors(self, self.wynn_active_preset)

def get_preset_items(self, context):
    if CACHE["presets"] is None:
        load_presets()
    
    items = []
    # Ensure keys exist
    keys = list(CACHE["presets"].keys())
    
    # Sort such that Default is always top or first
    if DEFAULT_PRESET_NAME in keys:
        keys.remove(DEFAULT_PRESET_NAME)
        keys.sort()
        keys.insert(0, DEFAULT_PRESET_NAME)
    else:
        keys.sort()
    
    # Format: (identifier, name, description)
    for k in keys:
        items.append((k, k, f"Select preset {k}"))
        
    return items

class WynnVertexColorItem(bpy.types.PropertyGroup):
    color: bpy.props.FloatVectorProperty(
        name="Color", subtype='COLOR', size=3, min=0.0, max=1.0, default=(1.0, 1.0, 1.0)
    )

class WYNN_OT_AddPreset(bpy.types.Operator):
    """Add a new custom preset based on the current one"""
    bl_idname = "wynn.add_preset"
    bl_label = "Add Preset"
    
    new_name: bpy.props.StringProperty(name="New Preset Name", default="MyPreset")
    
    def execute(self, context):
        name = self.new_name.strip()
        if not name:
            self.report({'ERROR'}, "Name cannot be empty")
            return {'CANCELLED'}
        
        if CACHE["presets"] is None:
            load_presets()
            
        if name in CACHE["presets"]:
            self.report({'ERROR'}, f"Preset '{name}' already exists")
            return {'CANCELLED'}

        # Capture current colors
        current_colors = {}
        for item in context.scene.wynn_vertex_colors:
            current_colors[item.name] = list(item.color)
            
        CACHE["presets"][name] = current_colors
        save_presets(CACHE["presets"])
        
        # Switch to new preset
        # We need to manually update the enum, but updating the property triggers the callback
        # However, the get_preset_items needs to run first. EnumProperty callbacks usually run on access.
        
        context.scene.wynn_active_preset = name
        # Force update because sometimes assigning same value (if it was somehow same) doesn't trigger
        # But here it's a new name, so it should trigger update_preset
        
        self.report({'INFO'}, f"Created preset '{name}'")
        return {'FINISHED'}
        
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class WYNN_OT_RemovePreset(bpy.types.Operator):
    """Remove the active custom preset"""
    bl_idname = "wynn.remove_preset"
    bl_label = "Remove Preset"
    
    @classmethod
    def poll(cls, context):
        return context.scene.wynn_active_preset != DEFAULT_PRESET_NAME

    def execute(self, context):
        name = context.scene.wynn_active_preset
        
        if CACHE["presets"] is None:
            load_presets()
            
        if name in CACHE["presets"] and name != DEFAULT_PRESET_NAME:
            del CACHE["presets"][name]
            save_presets(CACHE["presets"])
            
            # Revert to Default
            context.scene.wynn_active_preset = DEFAULT_PRESET_NAME
            self.report({'INFO'}, f"Removed preset '{name}'")
            return {'FINISHED'}
            
        return {'CANCELLED'}

class WYNN_OT_SavePreset(bpy.types.Operator):
    """Save changes to the current preset"""
    bl_idname = "wynn.save_preset"
    bl_label = "Save Preset"
    
    @classmethod
    def poll(cls, context):
        return context.scene.wynn_active_preset != DEFAULT_PRESET_NAME

    def execute(self, context):
        name = context.scene.wynn_active_preset
        
        if CACHE["presets"] is None:
            load_presets()
            
        new_data = {}
        for item in context.scene.wynn_vertex_colors:
            # We trust item.name is unique enough or last writer wins
            new_data[item.name] = list(item.color)
            
        CACHE["presets"][name] = new_data
        save_presets(CACHE["presets"])
        self.report({'INFO'}, f"Saved preset '{name}'")
        return {'FINISHED'}

class WYNN_OT_AddColor(bpy.types.Operator):
    """Add a new color to the current preset"""
    bl_idname = "wynn.add_color"
    bl_label = "Add Color"
    
    @classmethod
    def poll(cls, context):
        return context.scene.wynn_active_preset != DEFAULT_PRESET_NAME

    def execute(self, context):
        # Auto-generate unique name
        base_name = "Color"
        count = 1
        new_name = f"{base_name} {count}"
        
        existing_names = {item.name for item in context.scene.wynn_vertex_colors}
        while new_name in existing_names:
            count += 1
            new_name = f"{base_name} {count}"

        item = context.scene.wynn_vertex_colors.add()
        item.name = new_name
        item.color = (1.0, 1.0, 1.0)
        
        # Auto-save removed to allow manual save workflow
        # bpy.ops.wynn.save_preset()
        
        return {'FINISHED'}

class WYNN_OT_RemoveColor(bpy.types.Operator):
    """Remove a color from the current preset"""
    bl_idname = "wynn.remove_color"
    bl_label = "Remove Color"
    
    index: bpy.props.IntProperty()
    
    @classmethod
    def poll(cls, context):
        return context.scene.wynn_active_preset != DEFAULT_PRESET_NAME

    def execute(self, context):
        if 0 <= self.index < len(context.scene.wynn_vertex_colors):
            context.scene.wynn_vertex_colors.remove(self.index)
            # Auto-save removed to allow manual save workflow
            # bpy.ops.wynn.save_preset()  
        return {'FINISHED'}

class VertexColorIDPanel(bpy.types.Panel):
    """Creates a Panel in the 3D view's tool shelf"""
    bl_label = "Vertex Color ID"
    bl_idname = "OBJECT_PT_vertex_color_id"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Only show the panel in Edit Mode
        if context.mode != 'EDIT_MESH':
            layout.label(text="Tool only works in Edit Mode")
            return

        # Initialize if empty (fallback for when load_post might have missed or new scene)
        if len(scene.wynn_vertex_colors) == 0:
            layout.label(text="No colors loaded. Switch Preset.")
            # Trigger update implicitly by showing the enum
        
        # Preset Management
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(scene, "wynn_active_preset", text="")
        row.operator("wynn.add_preset", text="", icon='ADD')
        
        sub = row.row(align=True)
        sub.enabled = (scene.wynn_active_preset != DEFAULT_PRESET_NAME)
        sub.operator("wynn.remove_preset", text="", icon='REMOVE')
        
        layout.separator()

        # Color List
        for i, item in enumerate(scene.wynn_vertex_colors):
            box = layout.box()
            row = box.row(align=True)
            
            # Color Property
            # If Default, color modification is temporary (until reset) or allowed?
            # User said "cannot change inside Default". So disable if Default.
            sub_col = row.row(align=True)
            if scene.wynn_active_preset == DEFAULT_PRESET_NAME:
                sub_col.enabled = False
            sub_col.prop(item, "color", text="")
            
            # Name Label/Entry
            # row.label(text=item.name)
            # Make name editable? Prompt implied "User can add new colors". 
            # Doesn't explicitly say rename. Labels are safer.
            # Name is not displayed as per user request
            # row.label(text=item.name)

            # Assign / Select
            sub = row.row(align=True)
            op_assign = sub.operator("mesh.assign_vertex_color", text="Assign")
            op_assign.color = item.color
            
            op_select = sub.operator("mesh.select_by_vertex_color", text="Select")
            op_select.color = item.color
            
            # Remove Button (Only for Custom)
            if scene.wynn_active_preset != DEFAULT_PRESET_NAME:
                op_rem = row.operator("wynn.remove_color", text="", icon='X')
                op_rem.index = i

        if scene.wynn_active_preset != DEFAULT_PRESET_NAME:
            layout.separator()
            row = layout.row()
            row.operator("wynn.add_color", text="Add New Color", icon='ADD')
            
            # Save button (Explicit save for modifications to color values)
            row.operator("wynn.save_preset", text="Save Preset", icon='FILE_TICK')
            
            # Check if dirty (unsaved changes)
            is_dirty = False
            preset_name = scene.wynn_active_preset
            saved_data = CACHE["presets"].get(preset_name, {})
            
            # Check length mismatch
            if len(scene.wynn_vertex_colors) != len(saved_data):
                is_dirty = True
            else:
                # Check for content mismatch
                # Note: This checks if all current items exist in saved data with same values.
                # It assumes order might matter for UI but here using dict lookup for robust check.
                # Iterate over current items
                for item in scene.wynn_vertex_colors:
                    if item.name not in saved_data:
                        is_dirty = True
                        break
                    
                    saved_col = saved_data[item.name]
                    # Check color values with small epsilon
                    if (abs(item.color[0] - saved_col[0]) > 1e-4 or
                        abs(item.color[1] - saved_col[1]) > 1e-4 or
                        abs(item.color[2] - saved_col[2]) > 1e-4):
                        is_dirty = True
                        break
            
            if is_dirty:
                layout.separator()
                layout.label(text="* อย่าลืมกด Save Preset", icon='INFO')

        layout.separator()
        layout.operator("geometry.remove_color_attribute_confirm", text="Remove Color Attribute", icon='TRASH')


class AssignVertexColor(bpy.types.Operator):
    """Assigns a vertex color to the selected vertices"""
    bl_idname = "mesh.assign_vertex_color"
    bl_label = "Assign Vertex Color"
    bl_options = {'REGISTER', 'UNDO'}

    color: bpy.props.FloatVectorProperty(name="Color", subtype='COLOR', size=3, default=(1.0, 1.0, 1.0))

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'EDIT_MESH'

    def execute(self, context):
        bpy.ops.object.mode_set(mode='VERTEX_PAINT')
        context.space_data.shading.color_type = 'VERTEX'
        context.object.data.use_paint_mask = True
        
        # Set the brush color
        if context.scene.tool_settings.vertex_paint.unified_paint_settings:
             context.scene.tool_settings.vertex_paint.unified_paint_settings.color = self.color
        else:
             # Fallback if unified settings not available (usually are)
             pass
             # Actually vertex paint brush color:
             if context.tool_settings.vertex_paint.brush:
                 context.tool_settings.vertex_paint.brush.color = self.color

        bpy.ops.paint.vertex_color_set()
        bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}

class SelectByVertexColor(bpy.types.Operator):
    """Selects vertices by their color"""
    bl_idname = "mesh.select_by_vertex_color"
    bl_label = "Select by Vertex Color"
    bl_options = {'REGISTER', 'UNDO'}

    color: bpy.props.FloatVectorProperty(name="Color", subtype='COLOR', size=3, default=(1.0, 1.0, 1.0))

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'EDIT_MESH'

    def execute(self, context):
        obj = context.active_object
        mesh = obj.data

        if not mesh.vertex_colors:
            self.report({'WARNING'}, "No vertex colors found on this mesh.")
            return {'CANCELLED'}

        bm = bmesh.from_edit_mesh(mesh)
        
        # Get active color layer
        color_layer = bm.loops.layers.color.active
        if not color_layer:
            self.report({'WARNING'}, "No active vertex color layer.")
            return {'CANCELLED'}

        # Deselect all geometry first
        for v in bm.verts:
            v.select = False
        for e in bm.edges:
            e.select = False
        for f in bm.faces:
            f.select = False

        target_color = self.color

        for face in bm.faces:
            for loop in face.loops:
                vert_color = loop[color_layer]
                
                # Compare RGB with tolerance (ignore Alpha)
                if (abs(vert_color[0] - target_color[0]) < 0.01 and
                    abs(vert_color[1] - target_color[1]) < 0.01 and
                    abs(vert_color[2] - target_color[2]) < 0.01):
                    
                    loop.vert.select = True

        bm.select_flush(True)
        bmesh.update_edit_mesh(mesh)

        return {'FINISHED'}


class RemoveColorAttributeConfirm(bpy.types.Operator):
    """Remove the active color attribute with confirmation"""
    bl_idname = "geometry.remove_color_attribute_confirm"
    bl_label = "Remove Color Attribute"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        bpy.ops.geometry.color_attribute_remove()
        return {'FINISHED'}

@persistent
def load_handler(dummy):
    # Initialize cache and scene data on load
    if CACHE["presets"] is None:
        load_presets()
    
    for scene in bpy.data.scenes:
        if len(scene.wynn_vertex_colors) == 0:
            p = scene.wynn_active_preset
            # If empty (default enum value might be 0 or '') or not valid, enforce Default
            if not p or p not in CACHE["presets"]:
                scene.wynn_active_preset = DEFAULT_PRESET_NAME
                p = DEFAULT_PRESET_NAME
            
            populate_colors(scene, p)

def register():
    bpy.utils.register_class(WynnVertexColorItem)
    bpy.types.Scene.wynn_vertex_colors = bpy.props.CollectionProperty(type=WynnVertexColorItem)
    bpy.types.Scene.wynn_active_preset = bpy.props.EnumProperty(
        name="Preset",
        description="Select Vertex Color Preset",
        items=get_preset_items,
        update=update_preset
    )
    
    bpy.utils.register_class(WYNN_OT_AddPreset)
    bpy.utils.register_class(WYNN_OT_RemovePreset)
    bpy.utils.register_class(WYNN_OT_SavePreset)
    bpy.utils.register_class(WYNN_OT_AddColor)
    bpy.utils.register_class(WYNN_OT_RemoveColor)
    bpy.utils.register_class(VertexColorIDPanel)
    bpy.utils.register_class(AssignVertexColor)
    bpy.utils.register_class(SelectByVertexColor)
    bpy.utils.register_class(RemoveColorAttributeConfirm)
    
    bpy.app.handlers.load_post.append(load_handler)
    
    # Try to initialize immediately for current session
    # (Because load_post only fires on file load)
    try:
        load_handler(None)
    except:
        pass


def unregister():
    if load_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(load_handler)

    del bpy.types.Scene.wynn_vertex_colors
    del bpy.types.Scene.wynn_active_preset
    
    bpy.utils.unregister_class(WynnVertexColorItem)
    bpy.utils.unregister_class(WYNN_OT_AddPreset)
    bpy.utils.unregister_class(WYNN_OT_RemovePreset)
    bpy.utils.unregister_class(WYNN_OT_SavePreset)
    bpy.utils.unregister_class(WYNN_OT_AddColor)
    bpy.utils.unregister_class(WYNN_OT_RemoveColor)
    bpy.utils.unregister_class(VertexColorIDPanel)
    bpy.utils.unregister_class(AssignVertexColor)
    bpy.utils.unregister_class(SelectByVertexColor)
    bpy.utils.unregister_class(RemoveColorAttributeConfirm)

    # Note: We are not removing the legacy properties "wynn_color_*" to catch possible lingering errors, 
    # but they won't be used. If full cleanup needed:
    # ...

if __name__ == "__main__":
    register()
