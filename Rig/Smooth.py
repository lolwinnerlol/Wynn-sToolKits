import bpy

class WYNN_OT_smooth_weights(bpy.types.Operator):
    """Smooth weights on the active vertex group, and if it's a symmetrical group (e.g., .L), smooth the other side as well."""
    bl_idname = "wynn.smooth_weights"
    bl_label = "Smooth Weights Symmetrically"
    bl_options = {'REGISTER', 'UNDO'}

    factor: bpy.props.FloatProperty(
        name="Factor",
        description="Intensity of the smoothing",
        default=0.5,
        min=0.0,
        max=1.0
    )

    iterations: bpy.props.IntProperty(
        name="Iterations",
        description="Number of times to repeat smoothing",
        default=1,
        min=1
    )

    @classmethod
    def poll(cls, context):
        return (context.object is not None and
                context.object.type == 'MESH' and
                context.object.mode == 'WEIGHT_PAINT' and
                context.object.vertex_groups.active is not None)

    def execute(self, context):
        obj = context.object
        active_group = obj.vertex_groups.active
        active_group_name = active_group.name

        # Initial smooth on the active group
        bpy.ops.object.vertex_group_smooth(factor=self.factor, repeat=self.iterations)
        bpy.ops.object.vertex_group_normalize_all(group_select_mode='BONE_DEFORM')


        # Check for symmetrical group and smooth the counterpart
        symmetrical_group_name = self.get_symmetrical_group(active_group_name)
        if symmetrical_group_name and symmetrical_group_name in obj.vertex_groups:
            # Store the original active group index
            original_active_group_index = obj.vertex_groups.active_index
            
            # Set the symmetrical group as active
            obj.vertex_groups.active_index = obj.vertex_groups[symmetrical_group_name].index
            
            # Smooth the symmetrical group
            bpy.ops.object.vertex_group_smooth(factor=self.factor, repeat=self.iterations)
            bpy.ops.object.vertex_group_normalize_all(group_select_mode='BONE_DEFORM')

            
            # Restore the original active group
            obj.vertex_groups.active_index = original_active_group_index

        self.report({'INFO'}, f"Smoothed '{active_group_name}'" + (f" and '{symmetrical_group_name}'" if symmetrical_group_name else ""))
        return {'FINISHED'}

    def get_symmetrical_group(self, name):
        """Gets the symmetrical counterpart of a vertex group name."""
        endings = {'.L': '.R', '_L': '_R', '.R': '.L', '_R': '_L', '.l': '.r', '.r': '.l'}
        for suffix, opposite in endings.items():
            if name.endswith(suffix):
                return name[:-len(suffix)] + opposite
        return None

def register():
    bpy.utils.register_class(WYNN_OT_smooth_weights)

def unregister():
    bpy.utils.unregister_class(WYNN_OT_smooth_weights)

if __name__ == "__main__":
    register()
