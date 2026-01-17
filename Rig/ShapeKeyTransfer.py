import bpy

class WYNN_OT_transfer_shape_key(bpy.types.Operator):
    """Transfer the Active Shape Key from the Selected Source Mesh to the Active Target Mesh"""
    bl_idname = "wynn.transfer_shape_key"
    bl_label = "Transfer Shape Key"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH' and len(context.selected_objects) == 2

    def execute(self, context):
        target = context.active_object
        source = None
        
        # Find Source (Selected, Not Active)
        for obj in context.selected_objects:
            if obj != target:
                source = obj
                break
        
        if not source or source.type != 'MESH':
            self.report({'ERROR'}, "Select exactly two meshes (Source and Target)")
            return {'CANCELLED'}

        # Get Source Shape Key
        if not source.data.shape_keys:
             self.report({'ERROR'}, "Source mesh has no shape keys")
             return {'CANCELLED'}
        
        source_key = source.active_shape_key
        if not source_key:
             self.report({'ERROR'}, "No active shape key on source")
             return {'CANCELLED'}
             
        # Check Topology
        if len(source.data.vertices) != len(target.data.vertices):
            self.report({'ERROR'}, "Topology Mismatch: Vertex count differs")
            return {'CANCELLED'}
        
        # Transfer
        try:
            # Create Shape Keys block if missing
            if not target.data.shape_keys:
                target.shape_key_add(name="Basis")
            
            # Create New Key
            new_key = target.shape_key_add(name=source_key.name, from_mix=False)
            
            # Copy Points
            # Optimization: Use foreach_get/set for speed
            count = len(source.data.vertices)
            coords = [0.0] * (3 * count)
            
            # Get coords from source key relative to... wait, shape keys store absolute coords in local space
            source_key.data.foreach_get("co", coords)
            new_key.data.foreach_set("co", coords)
            
            # Copy other properties
            new_key.value = source_key.value
            new_key.slider_min = source_key.slider_min
            new_key.slider_max = source_key.slider_max
            new_key.vertex_group = source_key.vertex_group # This might be invalid if group names differ, but we copy the string info
            
            self.report({'INFO'}, f"Transferred '{source_key.name}' to '{target.name}'")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Transfer Failed: {e}")
            return {'CANCELLED'}

class WYNN_PT_shape_key_transfer(bpy.types.Panel):
    """Panel for Transfer Shape Key Tool"""
    bl_label = "Shape Key Transfer"
    bl_idname = "WYNN_PT_shape_key_transfer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Wynn'
    
    def draw(self, context):
        layout = self.layout
        
        # Identify Source/Target for UI feedback
        target = context.active_object
        source = None
        if context.selected_objects:
             for obj in context.selected_objects:
                if obj != target:
                    source = obj
                    break
        
        col = layout.column(align=True)
        
        # Source Info
        row = col.row()
        row.label(text="Source:")
        if source:
            row.label(text=source.name, icon='MESH_DATA')
            if source.type == 'MESH' and source.data.shape_keys and source.active_shape_key:
                col.label(text=f"Key: {source.active_shape_key.name}", icon='SHAPEKEY_DATA')
            else:
                 col.label(text="(No Active Shape Key)", icon='ERROR')
        else:
            row.label(text="None (Select 1 more)", icon='ERROR')
            
        col.separator()
            
        # Target Info
        row = col.row()
        row.label(text="Target:")
        if target:
            row.label(text=target.name, icon='MESH_DATA')
        else:
            row.label(text="None", icon='ERROR')
            
        col.separator()
        
        # Button
        sub = col.column()
        sub.enabled = (source is not None and target is not None and source.type == 'MESH' and target.type == 'MESH')
        sub.operator("wynn.transfer_shape_key", text="Transfer Active Key", icon='IMPORT')

def register():
    bpy.utils.register_class(WYNN_OT_transfer_shape_key)
    bpy.utils.register_class(WYNN_PT_shape_key_transfer)

def unregister():
    bpy.utils.unregister_class(WYNN_OT_transfer_shape_key)
    bpy.utils.unregister_class(WYNN_PT_shape_key_transfer)
