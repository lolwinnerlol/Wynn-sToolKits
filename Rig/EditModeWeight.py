import bpy
import bmesh
import ctypes
import os
import time

# --- UTILS ---
def get_dll_path():
    return os.path.join(os.path.dirname(__file__), "WynnWeightLogic.dll")

class WynnEditWeightBase(bpy.types.Operator):
    """Base class for Edit Mode Weight Operations"""
    bl_options = {'REGISTER', 'UNDO'}

    def check_falloff_pref(self, context):
        # Only override if NOT set by user (or passing in args)
        if self.properties.is_property_set("use_falloff"):
            return

        try:
            addon_name = __package__.split('.')[0]
            prefs = context.preferences.addons.get(addon_name)
            if prefs and prefs.preferences.edit_mode_use_falloff:
                self.use_falloff = True
        except Exception as e:
            print(f"WynnEditWeight Pref Error: {e}")

    def get_falloff_targets(self, bm, selected_verts, steps):
        """
        Returns dict {bm_vert: factor}
        Selected verts = 1.0
        Outer rings fade linearly to 0.0
        """
        weights = {v: 1.0 for v in selected_verts}
        if steps <= 0: return weights
        
        visited = set(selected_verts)
        current_ring = set(selected_verts)
        
        # Total distance = steps + 1 to reach 0
        # step 1: factor = (steps) / (steps+1) ?
        # e.g. steps=1. Ring 1 has factor 0.5?
        # Let's try simple linear: 1.0 -> 0.0 over (steps+1) segments
        
        for i in range(1, steps + 1):
            next_ring = set()
            factor = (steps - i + 1) / (steps + 1)
            
            for v in current_ring:
                for e in v.link_edges:
                    other = e.other_vert(v)
                    if other not in visited:
                        visited.add(other)
                        next_ring.add(other)
                        weights[other] = factor
            
            if not next_ring: break
            current_ring = next_ring
            
        return weights

    def get_active_group_index(self, obj, bm=None, selected_verts=None):
        # 1. Check for Active Bone (Priority 1)
        # If user explicitly selected a bone in Pose Mode, they imply intent.
        armature = None
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object:
                armature = mod.object
                break
        
        if armature and armature.mode == 'POSE':
            active_bone = armature.data.bones.active
            if active_bone and active_bone.select: # Must be selected
                 g = obj.vertex_groups.get(active_bone.name)
                 if g: return g.index

        # 2. Check Obj Active Index (Priority 2, but only if "valid")
        # If user MANUALLY set index in properties panel, maybe respect it?
        # But user says "user wont select vertex group". So this is untrusted.
        
        # 3. Auto-Detect from Selection (Priority 3 - Fallback)
        # Find the group with the Highest Average Weight across selected vertices.
        if bm and selected_verts:
            dvert_layout = bm.verts.layers.deform.verify()
            group_sums = {}
            for v in selected_verts:
                dvert = v[dvert_layout]
                for g, w in dvert.items():
                    if w > 0.001:
                        group_sums[g] = group_sums.get(g, 0.0) + w
            
            if group_sums:
                # Return group with max total weight
                best_group = max(group_sums, key=group_sums.get)
                print(f"[AutoDetect] Picked Group {best_group} based on selection.")
                return best_group

        # 4. Fallback to Obj Active
        return obj.vertex_groups.active_index

    def get_c_arrays(self, bm, selected_verts, active_group_index):
        """
        Extract BMesh data into C-compatible arrays.
        Returns: (c_weight_indices, c_weight_values, target_indices, base_offset_map)
        
        Note: C++ expects a FLATTENED array of ALL vertices (index*8). 
        To avoid allocating 8 floats * 100k verts for just 5 selected verts,
        we might need a mapping?
        
        WAIT: The C++ `smooth_strided` and `apply_vertex_logic_strided` 
        take `weight_indices` ptr and `v_idx * stride`.
        They assume a full buffer exists.
        
        Workaround for Sparse Edit Mode:
        We will allocate a buffer JUST large enough for the MAXIMUM index in selected_verts?
        No, that's wasteful if we select vert #100000.
        
        Strategy:
        We will pass a "virtual" buffer to C++.
        But C++ uses `v_idx * stride` to index into it.
        We cannot easily change C++ logic without recompiling.
        
        Alternative:
        We re-map vertex indices to local 0..N range for the C++ call.
        Py: {RealID: LocalID}
        C: receives LocalIDs.
        
        Issue: Adjacency (Smooth) relies on real topology indices.
        If we remap, Adjacency indices must also be remapped.
        
        Conclusion:
        For `apply_vertex_logic_strided` (Assign/Harden), it does NOT use adjacency.
        So we can Remap indices easily.
            - real_indices = [105, 209, ...]
            - c_indices = [0, 1, ...]
            - c_weights = [weight data for 0..N]
            - Pass c_indices 0..N to C++.
            - Write back to real_indices.
            
        For `smooth_strided` (Smooth):
        It USES adjacency. Adjacency is built on Mesh indices.
        If we rebuild adjacency for just selected + neighbors, we can use Local IDs.
        
        Step 1: Identify "Working Set" (Selected + Neighbors).
        Step 2: Map RealID -> LocalID.
        Step 3: Build Adjacency for LocalIDs.
        Step 4: Build Weights for LocalIDs.
        Step 5: Run C++.
        Step 6: Write back.
        """
        pass

    def load_dll(self):
        dll_path = get_dll_path()
        if not os.path.exists(dll_path):
            self.report({'ERROR'}, "DLL not found")
            return None
        
        try:
            dll = ctypes.CDLL(dll_path)
            return dll
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load DLL: {e}")
            return None



class WYNN_OT_harden_weights(WynnEditWeightBase):
    """Harden weights of selected vertices (Push to 0 or 1)"""
    bl_idname = "wynn.edit_harden_weights"
    bl_label = "Harden Weight (Edit)"
    
    factor: bpy.props.FloatProperty(name="Factor", default=1.0, min=0.0, max=1.0)
    
    use_falloff: bpy.props.BoolProperty(name="Use Falloff", default=False)
    falloff_factor: bpy.props.FloatProperty(name="Falloff Factor", default=1.0, min=0.0, max=2.0)
    falloff_steps: bpy.props.IntProperty(name="Falloff Steps", default=2, min=1, max=10)
    
    def execute(self, context):
        # Re-use Assign logic but change mode to HARDEN (1)
        # We need to minimally override because Assign has 'weight_value' which we don't need for Harden
        # but the structure is identical.
        self.check_falloff_pref(context)
        
        obj = context.active_object
        if obj.mode != 'EDIT' or obj.type != 'MESH':
            return {'CANCELLED'}

        bm = bmesh.from_edit_mesh(obj.data)
        
        selected_verts = [v for v in bm.verts if v.select]
        if not selected_verts: return {'FINISHED'}
        
        active_index = self.get_active_group_index(obj, bm, selected_verts)
        if active_index == -1: return {'CANCELLED'}

        dvert_layout = bm.verts.layers.deform.verify()

        if self.use_falloff:
            falloff_map = self.get_falloff_targets(bm, selected_verts, self.falloff_steps)
            target_verts = list(falloff_map.keys())
        else:
            target_verts = selected_verts
            falloff_map = {v: self.factor for v in target_verts} # If no falloff, all use global factor
            
        # Prepare Data
        num_targets = len(target_verts)
        stride = 8
        
        c_weight_indices = (ctypes.c_int * (num_targets * stride))()
        c_weight_values = (ctypes.c_float * (num_targets * stride))()
        c_target_indices = (ctypes.c_int * num_targets)()
        c_target_factors = (ctypes.c_float * num_targets)()
        
        # Init
        ctypes.memset(c_weight_indices, 0xFF, ctypes.sizeof(c_weight_indices))
        
        print(f"[Harden] Processing {num_targets} verts. Falloff={self.use_falloff}")
        
        for i, v in enumerate(target_verts):
            c_target_indices[i] = i
            
            # Factor:
            # If falloff: factor = local_factor * falloff_factor * self.factor
            # Or just local_factor? Usually factor * local_factor.
            local_factor = falloff_map.get(v, 1.0)
            if self.use_falloff:
                 c_target_factors[i] = local_factor * self.factor * self.falloff_factor
            else:
                 c_target_factors[i] = self.factor 
            
            dvert = v[dvert_layout]
            col = 0
            found_active = False
            for g, w in dvert.items():
                if col >= 8: break
                c_weight_indices[i*8 + col] = g
                c_weight_values[i*8 + col] = w
                if g == active_index: found_active = True
                col += 1
            
            if i < 5: # Debug first 5
                print(f"  V[{v.index}] Active({active_index}) Found={found_active} Weights={dvert.items()}")

        dll = self.load_dll()
        if not dll: return {'CANCELLED'}
        
        try:
             dll.apply_vertex_logic_strided.argtypes = [
                ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_float),
                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_float
            ]
        except AttributeError:
             self.report({'ERROR'}, "DLL Outdated: apply_vertex_logic_strided missing")
             return {'CANCELLED'}
        
        # Mode 1 = Harden
        dll.apply_vertex_logic_strided(
            c_weight_indices, c_weight_values,
            c_target_indices, c_target_factors,
            num_targets, active_index, 1, 0.0
        )
        
        # Write Back
        for i, v in enumerate(target_verts):
            dvert = v[dvert_layout]
            base = i * 8
            
            new_map = {}
            for k in range(8):
                g = c_weight_indices[base + k]
                w = c_weight_values[base + k]
                if g >= 0 and w > 0.0001:
                    new_map[g] = w
            
            # Debug change
            if i < 5:
                 old_w = dvert.get(active_index, 0.0)
                 new_w = new_map.get(active_index, 0.0)
                 print(f"  V[{v.index}] {old_w:.3f} -> {new_w:.3f}")

            dvert.clear()
            for g, w in new_map.items():
                dvert[g] = w
                
        bmesh.update_edit_mesh(obj.data)
        self.report({'INFO'}, f"Hardened {len(target_verts)} verts (Falloff={self.use_falloff}, Group={active_index})")
        return {'FINISHED'}

class WYNN_OT_smooth_weights(WynnEditWeightBase):
    """Smooth weights of selected vertices (using C++ Adjacency)"""
    bl_idname = "wynn.edit_smooth_weights"
    bl_label = "Smooth Weights (Edit)"
    
    factor: bpy.props.FloatProperty(name="Factor", default=0.5, min=0.0, max=1.0)
    iterations: bpy.props.IntProperty(name="Iterations", default=1, min=1, max=10)
    
    use_falloff: bpy.props.BoolProperty(name="Use Falloff", default=False)
    falloff_factor: bpy.props.FloatProperty(name="Falloff Factor", default=1.0, min=0.0, max=2.0)
    falloff_steps: bpy.props.IntProperty(name="Falloff Steps", default=2, min=1, max=10)


    def execute(self, context):
        self.check_falloff_pref(context)
        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)
        dvert_layout = bm.verts.layers.deform.verify()
        
        selected_verts = [v for v in bm.verts if v.select]
        if not selected_verts: return {'FINISHED'}
        
        if self.use_falloff:
            falloff_map = self.get_falloff_targets(bm, selected_verts, self.falloff_steps)
            target_verts = list(falloff_map.keys())
        else:
            target_verts = selected_verts
            falloff_map = {v: 1.0 for v in selected_verts}
            
        # 1. Build "Working Set": Selected + Neighbors
        working_set = set(target_verts)
        for v in target_verts:
            for e in v.link_edges:
                working_set.add(e.other_vert(v))
        
        working_list = list(working_set)
        # Map Real -> Local
        local_map = {v.index: i for i, v in enumerate(working_list)}
        num_working = len(working_list)
        
        # 2. Build Mini-Adjacency (Python -> C++)
        print(f"[Smooth] Processing {len(target_verts)} targets. Working Set: {num_working}. Falloff={self.use_falloff}")
        
        # ... (Adjacency Building - Copied from original) ...
        adj_starts = [0] * (num_working + 1)
        adj_indices = []
        adj_weights = []
        
        neighbors = [[] for _ in range(num_working)]
        
        for v in working_list:
            v_idx = local_map[v.index]
            for e in v.link_edges:
                other = e.other_vert(v)
                if other.index in local_map:
                    other_idx = local_map[other.index]
                    dist = e.calc_length()
                    w = 1.0 / (dist + 0.0001)
                    neighbors[v_idx].append((other_idx, w))
        
        cursor = 0
        for i in range(num_working):
            adj_starts[i] = cursor
            for n_idx, w in neighbors[i]:
                adj_indices.append(n_idx)
                adj_weights.append(w)
                cursor += 1
            adj_starts[i+1] = cursor 
            
        c_adj_starts = (ctypes.c_int * len(adj_starts))(*adj_starts)
        c_adj_indices = (ctypes.c_int * len(adj_indices))(*adj_indices)
        c_adj_weights = (ctypes.c_float * len(adj_weights))(*adj_weights)
        
        # 3. Weights Buffer
        stride = 8
        c_weight_indices = (ctypes.c_int * (num_working * stride))()
        c_weight_values = (ctypes.c_float * (num_working * stride))()
        ctypes.memset(c_weight_indices, 0xFF, ctypes.sizeof(c_weight_indices))
        
        # Create map of Original Weights for blending later
        original_weights_map = {} # {RealID: {Group: Weight}}

        for i, v in enumerate(working_list):
            dvert = v[dvert_layout]
            
            # Save original for blending
            original_weights_map[v.index] = {g: w for g, w in dvert.items()}
            
            col = 0
            for g, w in dvert.items():
                if col >= stride: break
                c_weight_indices[i*stride + col] = g
                c_weight_values[i*stride + col] = w
                col += 1
        
        # 4. Target Indices (Local IDs)
        targets_local = [local_map[v.index] for v in target_verts]
        c_targets = (ctypes.c_int * len(targets_local))(*targets_local)
        
        # 5. Call C++
        dll = self.load_dll()
        if not dll: return {'CANCELLED'}
        
        dll.smooth_strided.argtypes = [
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(ctypes.c_int), ctypes.c_int, ctypes.c_float
        ]
        
        for _ in range(self.iterations):
            dll.smooth_strided(
                c_adj_starts, c_adj_indices, c_adj_weights,
                c_weight_indices, c_weight_values,
                c_targets, len(targets_local), self.factor # Factor applied in C++ is strict Lerp towards average
            )
            
        # 6. Write Back with Falloff Blend
        for v_idx_local in targets_local:
            real_v = working_list[v_idx_local]
            dvert = real_v[dvert_layout]
            base = v_idx_local * stride
            
            # Parse C++ Result (Smoothed)
            smoothed_map = {}
            for k in range(stride):
                g = c_weight_indices[base + k]
                w = c_weight_values[base + k]
                if g >= 0 and w > 0.0001:
                    smoothed_map[g] = w
            
            # Logic: Final = Lerp(Original, Smoothed, falloff_factor)
            # Use falloff_factor to scale the blend
            local_falloff = falloff_map.get(real_v, 1.0)
            final_blend = local_falloff * self.falloff_factor
            
            if final_blend >= 0.99:
                 final_map = smoothed_map
            else:
                 # Blend
                 # Need union of keys
                 orig = original_weights_map[real_v.index]
                 all_keys = set(orig.keys()) | set(smoothed_map.keys())
                 final_map = {}
                 
                 for g in all_keys:
                     w_orig = orig.get(g, 0.0)
                     w_new = smoothed_map.get(g, 0.0)
                     w_final = w_orig * (1.0 - final_blend) + w_new * final_blend
                     if w_final > 0.0001:
                         final_map[g] = w_final
            
            dvert.clear()
            for g, w in final_map.items():
                dvert[g] = w
                
        bmesh.update_edit_mesh(obj.data)
        return {'FINISHED'}

class WYNN_OT_add_weight(WynnEditWeightBase):
    """Add weight to selected vertices (Normalize Auto)"""
    bl_idname = "wynn.edit_add_weight"
    bl_label = "Add Weight (Edit)"
    bl_options = {'REGISTER', 'UNDO'}

    strength: bpy.props.FloatProperty(name="Strength", default=0.1, min=-1.0, max=1.0)
    
    use_falloff: bpy.props.BoolProperty(name="Use Falloff", default=False)
    falloff_factor: bpy.props.FloatProperty(name="Falloff Factor", default=1.0, min=0.0, max=2.0)
    falloff_steps: bpy.props.IntProperty(name="Falloff Steps", default=2, min=1, max=10)
    
    auto_normalize: bpy.props.BoolProperty(name="Auto Normalize", description="Subtract from other groups to maintain 1.0", default=False)

    def execute(self, context):
        self.check_falloff_pref(context)
        
        obj = context.active_object
        if obj.mode != 'EDIT' or obj.type != 'MESH':
            return {'CANCELLED'}

        bm = bmesh.from_edit_mesh(obj.data)
        dvert_layout = bm.verts.layers.deform.verify()
        
        selected_verts = [v for v in bm.verts if v.select]
        if not selected_verts: return {'FINISHED'}
        
        if not selected_verts: return {'FINISHED'}
        
        # Optimized Bone Detection (Priority: Active Bone -> Create Group if missing)
        active_index = -1
        
        # 0. Try to find Armature and Active Bone
        armature = None
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object:
                armature = mod.object
                break
        
        if armature:
            # Check Active Bone
            target_bone_name = None
            
            # If in Pose Mode, check pose bones
            if armature.mode == 'POSE':
               pbone = armature.pose.bones.get(armature.data.bones.active.name) if armature.data.bones.active else None
               if pbone and (pbone.bone.select or pbone.bone == armature.data.bones.active):
                   target_bone_name = pbone.name
            else:
               # Fallback to data active (e.g. if in Object mode but was selected)
               bone = armature.data.bones.active
               if bone and getattr(bone, 'select', True): # If select usage fails, assume active is enough or default True
                   target_bone_name = bone.name
            
            if target_bone_name:
                g = obj.vertex_groups.get(target_bone_name)
                if not g:
                    g = obj.vertex_groups.new(name=target_bone_name)
                    self.report({'INFO'}, f"Created Vertex Group: '{target_bone_name}'")
                active_index = g.index

        # Fallback to standard logic if no bone found
        if active_index == -1:
            active_index = self.get_active_group_index(obj, bm, selected_verts)
            
        if active_index == -1:
            self.report({'WARNING'}, "No active vertex group found")
            return {'CANCELLED'}

        # 1. Get Targets with Falloff
        if self.use_falloff:
            falloff_map = self.get_falloff_targets(bm, selected_verts, self.falloff_steps)
            target_verts = list(falloff_map.keys())
        else:
            target_verts = selected_verts
            falloff_map = {v: 1.0 for v in selected_verts}

        # 2. Add Weight & Normalize Loop
        count_changed = 0
        
        for v in target_verts:
            dvert = v[dvert_layout]
            
            # Helper to get current weight safely
            current_w = dvert.get(active_index, 0.0)
            
            # Calculate Delta
            # delta = strength * local_falloff * global_falloff_strength
            local_falloff = falloff_map.get(v, 1.0)
            if self.use_falloff:
                delta = self.strength * local_falloff * self.falloff_factor
            else:
                delta = self.strength # No falloff, uniform strength
            
            # New Weight (Un-normalized)
            raw_new_w = current_w + delta
            
            # Clamp 0..1 immediately? Normalization will handle ratios, 
            # but negative weights are invalid for storage usually.
            if raw_new_w < 0.0: raw_new_w = 0.0
            
            if self.auto_normalize:
                # Mode A: Auto-Normalize (Aggressive)
                # Ensure Total = 1.0. If active grows, others shrink.
                
                if raw_new_w >= 1.0:
                    # Active takes all
                    dvert.clear()
                    dvert[active_index] = 1.0
                else:
                    dvert[active_index] = raw_new_w
                    # Scale others to fit (1.0 - raw_new_w)
                    current_others_sum = sum(w for g, w in dvert.items() if g != active_index)
                    
                    if current_others_sum > 0.0001:
                        target_others_sum = 1.0 - raw_new_w
                        scale = target_others_sum / current_others_sum
                        for g in dvert.keys():
                            if g != active_index:
                                dvert[g] *= scale
                    else:
                        # If others are 0, we just have active weight (partial)
                        pass
            else:
                 # Mode B: Additive (Conservative)
                 # Only normalize if user overshoots 1.0 total
                 dvert[active_index] = raw_new_w
                 
                 # Normalize (Clamp to 1.0)
                 total_w = sum(dvert.values())
                 if total_w > 1.0001:
                     factor = 1.0 / total_w
                     for g in dvert.keys():
                         dvert[g] *= factor 
            
            count_changed += 1

        bmesh.update_edit_mesh(obj.data)
        
        group_name = obj.vertex_groups[active_index].name
        self.report({'INFO'}, f"Added Weight to {count_changed} verts (Bone: '{group_name}')")
        return {'FINISHED'}

class WYNN_OT_parent_binary_weights(bpy.types.Operator):
    """Placeholder for Parent Binary Weights"""
    bl_idname = "wynn.parent_binary_weights"
    bl_label = "Parent Binary"
    
    def execute(self, context):
        self.report({'INFO'}, "Parent Binary Not Implemented yet")
        return {'FINISHED'}

def register():
    bpy.utils.register_class(WYNN_OT_harden_weights)
    bpy.utils.register_class(WYNN_OT_smooth_weights)
    bpy.utils.register_class(WYNN_OT_add_weight)
    bpy.utils.register_class(WYNN_OT_parent_binary_weights)

def unregister():
    bpy.utils.unregister_class(WYNN_OT_harden_weights)
    bpy.utils.unregister_class(WYNN_OT_smooth_weights)
    bpy.utils.unregister_class(WYNN_OT_add_weight)
    bpy.utils.unregister_class(WYNN_OT_parent_binary_weights)
