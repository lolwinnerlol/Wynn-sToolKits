import bpy
import bmesh

COLORS_DICT = {
    "Red": (1, 0, 0),
    "Green": (0, 1, 0),
    "Blue": (0, 0, 1),
    "Yellow": (1, 1, 0),
    "Cyan": (0, 1, 1),
}

class VertexColorIDPanel(bpy.types.Panel):

    """Creates a Panel in the 3D view's tool shelf"""

    bl_label = "Vertex Color ID"
    bl_idname = "OBJECT_PT_vertex_color_id"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout

        # Only show the panel in Edit Mode
        if context.mode != 'EDIT_MESH':
            layout.label(text="Tool only works in Edit Mode")
            return

        for color_name in COLORS_DICT.keys():
            box = layout.box()
            
            # Add Assign and Select buttons
            row = box.row(align=True)
            
            prop_name = "wynn_color_" + color_name
            sub = row.row(align=True)
            sub.enabled = False
            sub.prop(context.scene, prop_name, text="")
            
            color_value = getattr(context.scene, prop_name)
            op_assign = row.operator("mesh.assign_vertex_color", text="Assign")
            op_assign.color = color_value
            
            op_select = row.operator("mesh.select_by_vertex_color", text="Select")
            op_select.color = color_value

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

        bpy.context.scene.tool_settings.vertex_paint.unified_paint_settings.color = self.color



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


def register():

    for name, value in COLORS_DICT.items():
        setattr(bpy.types.Scene, "wynn_color_" + name, bpy.props.FloatVectorProperty(
            name=name,
            subtype='COLOR',
            size=3,
            default=value
        ))

    bpy.utils.register_class(VertexColorIDPanel)
    bpy.utils.register_class(AssignVertexColor)
    bpy.utils.register_class(SelectByVertexColor)
    bpy.utils.register_class(RemoveColorAttributeConfirm)



def unregister():

    for name in COLORS_DICT.keys():
        if hasattr(bpy.types.Scene, "wynn_color_" + name):
            delattr(bpy.types.Scene, "wynn_color_" + name)

    bpy.utils.unregister_class(VertexColorIDPanel)
    bpy.utils.unregister_class(AssignVertexColor)
    bpy.utils.unregister_class(SelectByVertexColor)
    bpy.utils.unregister_class(RemoveColorAttributeConfirm)

if __name__ == "__main__":
    register()
