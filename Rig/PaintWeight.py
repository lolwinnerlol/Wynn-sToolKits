import bpy

def setup_weight_paint_viewport(context, mesh_obj, armature):
    """
    Sets up the viewport for an ideal weight painting session.
    - Enters Weight Paint mode
    - Sets armature to be in front
    - Makes deform bones visible
    - Sets brush to constant falloff
    """
    # Ensure we are in Object Mode to safely manipulate selection
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    armature.show_in_front = True

    if hasattr(armature.data, "collections"):
        for coll in armature.data.collections:
            if "deform" in coll.name.lower():
                coll.is_visible = True

    bpy.ops.object.select_all(action='DESELECT')
    armature.select_set(True)
    mesh_obj.select_set(True)
    context.view_layer.objects.active = mesh_obj

    bpy.ops.object.mode_set(mode='WEIGHT_PAINT')

    if context.tool_settings.weight_paint.brush:
        context.tool_settings.weight_paint.brush.curve_distance_falloff_preset = 'CONSTANT'

def get_child_meshes_items(self, context):
    items = []
    obj = context.active_object
    if obj and obj.type == 'ARMATURE':
        for child in obj.children:
            if child.type == 'MESH':
                items.append((child.name, child.name, child.name))
    
    if not items:
        items.append(('NONE', "None", "No child meshes found"))
    return items

class WYNN_OT_setup_weight_paint(bpy.types.Operator):
    """Manually sets up the viewport for weight painting. Toggles between Weight Paint and Object Mode."""
    bl_idname = "wynn.setup_weight_paint"
    bl_label = "Setup Weight Paint"
    bl_options = {'REGISTER', 'UNDO'}

    target_mesh: bpy.props.EnumProperty(
        name="Select Mesh",
        description="Select the mesh to weight paint",
        items=get_child_meshes_items
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and (obj.type == 'MESH' or obj.type == 'ARMATURE')

    def invoke(self, context, event):
        obj = context.active_object
        if obj and obj.type == 'ARMATURE':
            children = [c for c in obj.children if c.type == 'MESH']
            
            if len(children) > 1:
                # If one is already selected, default to it
                selected_children = [o for o in context.selected_objects if o in children]
                if selected_children:
                    self.target_mesh = selected_children[0].name
                return context.window_manager.invoke_props_dialog(self)
            elif len(children) == 1:
                self.target_mesh = children[0].name
        
        return self.execute(context)

    def execute(self, context):
        mesh_obj = None
        armature = None
        
        active = context.active_object
        
        # 1. Identify Mesh and Armature
        if active.type == 'MESH':
            mesh_obj = active
            # Check selection for armature
            for obj in context.selected_objects:
                if obj.type == 'ARMATURE':
                    armature = obj
                    break
            # Check parent
            if not armature and mesh_obj.parent and mesh_obj.parent.type == 'ARMATURE':
                armature = mesh_obj.parent
            # Check modifiers
            if not armature:
                for mod in mesh_obj.modifiers:
                    if mod.type == 'ARMATURE' and mod.object:
                        armature = mod.object
                        break
                        
        elif active.type == 'ARMATURE':
            armature = active
            
            # 1. Try property (from invoke dialog or default)
            if self.target_mesh and self.target_mesh != 'NONE':
                mesh_obj = bpy.data.objects.get(self.target_mesh)
            
            # 2. Fallback to selection
            if not mesh_obj:
                for obj in context.selected_objects:
                    if obj.type == 'MESH':
                        mesh_obj = obj
                        break
        
        if not mesh_obj:
            self.report({'WARNING'}, "No mesh found. Select a mesh or an armature with a selected mesh.")
            return {'CANCELLED'}

        # 2. Toggle Logic
        if mesh_obj.mode == 'WEIGHT_PAINT':
            # Toggle OFF: Return to Object Mode and restore viewport
            bpy.ops.object.mode_set(mode='OBJECT')
            if armature:
                armature.show_in_front = False
            self.report({'INFO'}, "Exited Weight Paint Mode.")
        else:
            # Toggle ON: Setup Weight Paint
            if not armature:
                self.report({'ERROR'}, "Could not find associated Armature for the mesh.")
                return {'CANCELLED'}
                
            setup_weight_paint_viewport(context, mesh_obj, armature)
            self.report({'INFO'}, "Weight paint viewport setup complete.")
            print("complete paint mode")
            
        return {'FINISHED'}

def register():
    bpy.utils.register_class(WYNN_OT_setup_weight_paint)

def unregister():
    bpy.utils.unregister_class(WYNN_OT_setup_weight_paint)