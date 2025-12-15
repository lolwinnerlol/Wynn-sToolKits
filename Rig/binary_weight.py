import bpy
import mathutils

def get_bone_deform_matrices(armature_obj, target_bone_names=None):
    """
    Returns a dictionary of bone names to their world space head/tail vectors.
    We use Edit Bones if in Edit Mode, otherwise Pose Bones.
    """
    bones = {}
    mw = armature_obj.matrix_world
    
    # We use pose bones to get the current state of the armature
    for pbone in armature_obj.pose.bones:
        # Check if bone is deform enabled
        if pbone.bone.use_deform:
            # Check selection if requested (filter by name list)
            if target_bone_names is not None and pbone.name not in target_bone_names:
                continue

            # Get head and tail in World Space
            head = mw @ pbone.head
            tail = mw @ pbone.tail
            bones[pbone.name] = (head, tail, pbone.bone.length)
            
    return bones

def get_distance_to_segment(v, a, b):
    """
    Calculates the squared distance from vertex v to the line segment ab.
    v: vertex point
    a: bone head
    b: bone tail
    Using squared distance is faster (avoids square roots).
    """
    ab = b - a
    av = v - a
    
    # Project v onto the line ab to find the closest point
    if ab.length_squared == 0:
        return (v - a).length_squared
        
    t = av.dot(ab) / ab.length_squared
    
    # Clamp t to the segment [0, 1]
    t = max(0.0, min(1.0, t))
    
    # Closest point on the segment
    closest_point = a + t * ab
    
    return (v - closest_point).length_squared

def apply_binary_weights(mesh_obj, armature_obj, target_bone_names=None):
    # 1. Get Mesh Data
    mesh = mesh_obj.data
    
    # 2. Get Bone Data (World Space)
    # Map: bone_name -> (head, tail, length)
    bone_data = get_bone_deform_matrices(armature_obj, target_bone_names=target_bone_names)
    bone_names = list(bone_data.keys())
    
    if not bone_names:
        return {'CANCELLED'}

    # 3. Create Vertex Groups
    # Clear old groups to ensure clean binary state
    mesh_obj.vertex_groups.clear()
    
    # Create groups and store references for speed
    group_lookup = {}
    for name in bone_names:
        group_lookup[name] = mesh_obj.vertex_groups.new(name=name)

    # 4. Calculation Loop
    # For every vertex, find the closest bone segment
    
    # Pre-calculate world space coordinates for all vertices
    mw = mesh_obj.matrix_world
    # Note: For massive meshes, we could use numpy here for speed
    verts_world = [mw @ v.co for v in mesh.vertices]
    
    print(f"Processing {len(verts_world)} vertices...")
    
    for i, v_pos in enumerate(verts_world):
        best_dist = float('inf')
        best_bone = None
        
        # Check against every bone
        for name, (head, tail, length) in bone_data.items():
            # Distance from point to line segment
            dist = get_distance_to_segment(v_pos, head, tail)
            
            if dist < best_dist:
                best_dist = dist
                best_bone = name
        
        # 5. Assign Weight
        # We assume every vertex has at least one bone.
        if best_bone:
            # Assign strictly 1.0
            group_lookup[best_bone].add([i], 1.0, 'REPLACE')

class WYNN_OT_parent_binary_weights(bpy.types.Operator):
    """Parent with Binary (1.0/0.0) Weights"""
    bl_idname = "wynn.parent_binary_weights"
    bl_label = "Parent Binary Weights"
    bl_options = {'REGISTER', 'UNDO'}

    use_selected_bones: bpy.props.BoolProperty(
        name="Selected Bones Only",
        description="Only calculate weights for selected bones",
        default=False
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        # Basic Selection Validation
        if len(context.selected_objects) < 2:
            self.report({'ERROR'}, "Select Mesh then Armature")
            return {'CANCELLED'}
            
        armature = context.active_object
        mesh_obj = None
        
        # Find the non-active selected object (the mesh)
        for obj in context.selected_objects:
            if obj != armature and obj.type == 'MESH':
                mesh_obj = obj
                break
                
        if not mesh_obj or armature.type != 'ARMATURE':
            self.report({'ERROR'}, "Active object must be Armature, selected must be Mesh")
            return {'CANCELLED'}

        # Handle Selection Logic (Blender 4.0+ fix for Bone.select removal)
        target_bone_names = None
        if self.use_selected_bones:
            # Switch to Pose Mode temporarily to get selection
            prev_mode = armature.mode
            if prev_mode != 'POSE':
                bpy.ops.object.mode_set(mode='POSE')
            
            target_bone_names = {pb.name for pb in context.selected_pose_bones}
            
            if prev_mode != 'POSE':
                bpy.ops.object.mode_set(mode=prev_mode)
                
            if not target_bone_names:
                self.report({'WARNING'}, "No bones selected in Pose Mode.")
                return {'CANCELLED'}

        # 1. Parent the mesh (Empty Groups)
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.parent_set(type='ARMATURE')
        
        # 2. Run the math
        res = apply_binary_weights(mesh_obj, armature, target_bone_names=target_bone_names)
        
        if res == {'CANCELLED'}:
            self.report({'WARNING'}, "No suitable bones found (check selection or deform settings).")
            return {'CANCELLED'}

        self.report({'INFO'}, "Binary Weights Applied.")
        return {'FINISHED'}
