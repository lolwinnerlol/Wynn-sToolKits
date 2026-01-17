import bpy
import gpu
import blf
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from mathutils.kdtree import KDTree
from bpy_extras import view3d_utils
import math
import time  # NEW: For performance timing
import ctypes

# --- UTILS ---


def get_harden_target(weight, factor):
    target = 1.0 if weight >= 0.5 else 0.0
    return weight + (target - weight) * factor

def get_smooth_target(weight, avg_weight, factor):
    return weight + (avg_weight - weight) * factor

# --- DRAWING ---
def draw_text_callback(self, context):
    font_id = 0
    blf.size(font_id, 20) 
    blf.color(font_id, 1, 1, 1, 1) 
    
    x = self.mouse_x + 30
    y = self.mouse_y - 20
    
    # 1. MESSAGES
    if self.message_timer > 0:
        blf.color(font_id, 1, 1, 0, 1) 
        blf.position(font_id, x, y + 30, 0)
        blf.draw(font_id, self.message_text)

    # 2. NAVIGATION
    if self.is_navigating_radius:
        blf.color(font_id, 1, 1, 1, 1)
        blf.position(font_id, x, y, 0)
        blf.draw(font_id, f"RESIZING (PIXELS): {int(self.radius_px)}")
        return

    if self.is_navigating_strength:
        blf.color(font_id, 0.5, 0.8, 1, 1)
        blf.position(font_id, x, y, 0)
        blf.draw(font_id, f"STRENGTH: {self.strength:.2f}")
        return

    # 3. MODES
    if self.is_harden:
        blf.color(font_id, 1, 0.2, 0.2, 1)
        blf.draw(font_id, f"MODE: HARDEN")
    elif self.is_blur:
        blf.color(font_id, 0.2, 1, 0.2, 1)
        blf.draw(font_id, f"MODE: BLUR")
    else:
        blf.color(font_id, 1, 0.8, 0.2, 1)
        blf.draw(font_id, f"MODE: SMEAR")
    
    # 4. INFO (Undo)
    blf.position(font_id, x, y - 25, 0)
    blf.color(font_id, 0.8, 0.8, 0.8, 1)
    debug_text = "ON" if self.debug_mode else "OFF"
    blf.draw(font_id, f"Undo: {len(self.undo_stack)} | Debug(D): {debug_text}")

    # 5. PERFORMANCE (NEW)
    blf.position(font_id, x, y - 50, 0)
    
    # Color coding based on lag
    if self.last_compute_time < 5.0:
        blf.color(font_id, 0.2, 1.0, 0.2, 1) # Green (Good)
    elif self.last_compute_time < 15.0:
        blf.color(font_id, 1.0, 1.0, 0.2, 1) # Yellow (Warning)
    else:
        blf.color(font_id, 1.0, 0.2, 0.2, 1) # Red (Bad)
        
    blf.draw(font_id, f"Compute: {self.last_compute_time:.2f} ms")

def draw_circles_callback(self, context):
    if not self.cursor_loc or self.world_radius <= 0: return
    
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(2.0)
    
    def get_circle(center, radius):
        coords = []
        if not context.region_data: return []
        region = context.region
        rv3d = context.region_data
        try:
            view_inv = rv3d.view_matrix.inverted()
        except AttributeError: return []
        camera_pos = view_inv.translation
        normal = (camera_pos - center).normalized()
        tangent = normal.cross(Vector((0, 0, 1)))
        if tangent.length < 0.001: tangent = normal.cross(Vector((0, 1, 0)))
        tangent.normalize()
        bitangent = normal.cross(tangent).normalized()
        for i in range(33):
            angle = 2 * math.pi * i / 32
            pos = center + (tangent * math.cos(angle) + bitangent * math.sin(angle)) * radius
            coords.append(pos)
        return coords

    if self.is_navigating_radius: color = (1.0, 1.0, 1.0, 1.0)
    elif self.is_navigating_strength: color = (0.5, 0.8, 1.0, 1.0)
    elif self.is_harden: color = (1.0, 0.2, 0.2, 1.0)
    elif self.is_blur: color = (0.2, 1.0, 0.2, 1.0)
    else: color = (1.0, 0.8, 0.2, 1.0)

    coords = get_circle(self.cursor_loc, self.world_radius)
    if coords:
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": coords})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
        
        if self.is_navigating_strength:
            inner_rad = self.world_radius * self.strength
            coords_inner = get_circle(self.cursor_loc, inner_rad)
            if coords_inner:
                batch_inner = batch_for_shader(shader, 'LINE_STRIP', {"pos": coords_inner})
                shader.uniform_float("color", (0.5, 0.8, 1.0, 0.5))
                batch_inner.draw(shader)
    


    gpu.state.line_width_set(1.0)
    gpu.state.blend_set('NONE')

class WYNN_MT_brush_context_menu(bpy.types.Menu):
    bl_label = "Brush Settings"
    bl_idname = "WYNN_MT_brush_context_menu"

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, "wynn_brush_radius", text="Radius")
        layout.prop(context.scene, "wynn_brush_strength", slider=True, text="Strength")

class WYNN_OT_smear_perf_monitor(bpy.types.Operator):
    """Hard Smear + Performance Monitor"""
    bl_idname = "wynn.smear_perf_monitor"
    bl_label = "Smear (Perf Monitor)"
    bl_options = {'REGISTER', 'UNDO'}

    radius_px: bpy.props.IntProperty(name="Radius (Px)", default=50, min=1, max=1000)
    strength: bpy.props.FloatProperty(name="Strength", default=0.5, min=0.01, max=1.0)

    debug_mode: bpy.props.BoolProperty(name="Debug Mode", default=False)

    def invoke(self, context, event):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Select a Mesh")
            return {'CANCELLED'}
        self.mesh_object = obj

        # --- C++ DLL SETUP ---
        import ctypes
        import os
        self.dll = None
        self.c_stride = 8 # Fixed stride matches C++
        
        dll_path = os.path.join(os.path.dirname(__file__), "WynnWeightLogic.dll")
        if os.path.exists(dll_path):
            try:
                # Robust loading for Windows
                if hasattr(os, 'add_dll_directory'):
                    dll_dir = os.path.dirname(dll_path)
                    try:
                        with os.add_dll_directory(dll_dir):
                            self.dll = ctypes.CDLL(dll_path)
                    except OSError:
                         # Fallback if add_dll_directory fails or path is weird
                         self.dll = ctypes.CDLL(dll_path)
                else:
                    self.dll = ctypes.CDLL(dll_path)
                # smooth_strided(adj_s, adj_i, adj_w, w_i, w_v, targets, num, factor)
                self.dll.smooth_strided.argtypes = [
                    ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_float),
                    ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_float),
                    ctypes.POINTER(ctypes.c_int), ctypes.c_int, ctypes.c_float
                ]
                
                # New Function: apply_vertex_logic_strided
                # (indices, values, target_indices, target_factors, num, active_group, mode, smear_val)
                try:
                    self.dll.apply_vertex_logic_strided.argtypes = [
                        ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_float),
                        ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_float),
                        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_float
                    ]
                except AttributeError:
                    print("WynnWeightBrush: apply_vertex_logic_strided MISSING (Old DLL?)")

                try:
                    self.dll.build_adjacency_graph.argtypes = [
                        ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_float),
                        ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_float)
                    ]
                except AttributeError:
                    print("WynnWeightBrush: build_adjacency_graph MISSING (Old DLL?)")

                print(f"WynnWeightBrush: Accelerated Core Loaded from {dll_path}")
            except OSError as e:
                print(f"WynnWeightBrush: DLL Found but Failed to Load: {e}")
        else:
            print(f"WynnWeightBrush: DLL NOT FOUND at {dll_path}")
        
 

        # 2. CACHE
        if not self.refresh_geometry(context, self.mesh_object):
            self.report({'ERROR'}, "Vertex mismatch")
            return {'CANCELLED'}

        # 3. ADJACENCY (Setup ONCE)
        t_adj_start = time.perf_counter()
        
        # Prepare Data
        vertices = obj.data.vertices
        edges = obj.data.edges
        num_verts = len(vertices)
        num_edges = len(edges)
        
        # Allocate C++ Arrays (CSR Adjacency)
        # Note: Weights and Indices size = num_edges * 2 (undirected)
        total_neighbors = num_edges * 2
        
        self.c_adj_starts = (ctypes.c_int * (num_verts + 1))()
        self.c_adj_indices = (ctypes.c_int * total_neighbors)()
        self.c_adj_weights = (ctypes.c_float * total_neighbors)()
        
        # Get Raw Data from Blender (Fastest way)
        raw_edge_indices = (ctypes.c_int * (num_edges * 2))()
        edges.foreach_get("vertices", raw_edge_indices)
        
        raw_vert_coords = (ctypes.c_float * (num_verts * 3))()
        vertices.foreach_get("co", raw_vert_coords)
        
        # Call C++ Builder
        if self.dll and hasattr(self.dll, 'build_adjacency_graph'):
            self.dll.build_adjacency_graph(
                num_verts, num_edges, raw_edge_indices, raw_vert_coords,
                self.c_adj_starts, self.c_adj_indices, self.c_adj_weights
            )
        else:
            # Fallback (Just in case)
            print("WARNING: Using Slow Python Adjacency fallback")
            raw_adj = [[] for _ in range(num_verts)]
            for edge in obj.data.edges:
                v1_idx, v2_idx = edge.vertices
                v1 = vertices[v1_idx]
                v2 = vertices[v2_idx]
                dist = (v1.co - v2.co).length
                weight = 1.0 / (dist + 0.0001)
                raw_adj[v1_idx].append((v2_idx, weight))
                raw_adj[v2_idx].append((v1_idx, weight))
            
            cursor = 0
            for i in range(num_verts):
                self.c_adj_starts[i] = cursor
                for n_idx, w in raw_adj[i]:
                    self.c_adj_indices[cursor] = n_idx
                    self.c_adj_weights[cursor] = w
                    cursor += 1
            self.c_adj_starts[num_verts] = cursor

        # Legacy Dict (Only needed for fallback paint mode, skip if C++ active?)
        # Optim: Skip population if self.dll is working to save time
        self.adjacency = {} 
        
        print(f"[Init] Fast Adjacency Build: {(time.perf_counter() - t_adj_start)*1000:.2f}ms")

        t_weights_start = time.perf_counter()
        # Flatten Weights (Strided)
        # Allocate: [num_verts * STRIDE]
        total_slots = num_verts * self.c_stride
        self.c_weight_indices = (ctypes.c_int * total_slots)()
        self.c_weight_values = (ctypes.c_float * total_slots)()
        
        # Init with -1/0.0
        # memset? ctypes init is 0. We need indices to be -1 or handle 0 carefully.
        # Python loop to fill is slow but only run on Invoke.
        # For 100k verts -> 800k slots. Python loop might take 0.5s. Acceptable for startup.
        
        # Initialize default state
        # (Actually ctypes initializes to 0. Group 0 is valid. So we MUST init to -1)
        # Fast fill? No easy way in pure Python without numpy.
        # We'll just rely on the loop below fulfilling it.
        # Pre-fill is safer.
        
        # Init with -1 (0xFFFFFFFF)
        # Replaced slow Python loop with memset
        t_memset = time.perf_counter()
        ctypes.memset(self.c_weight_indices, 0xFF, ctypes.sizeof(self.c_weight_indices))
        print(f"  [Init] Memset: {(time.perf_counter() - t_memset)*1000:.3f}ms")
        
        # Populate
        for i, v in enumerate(vertices):
            base = i * self.c_stride
            for k, g in enumerate(v.groups):
                if k >= self.c_stride: break # Max Storage Limit per vert (8)
                self.c_weight_indices[base + k] = g.group
                self.c_weight_values[base + k] = g.weight
        print(f"[Init] Populate Weights: {(time.perf_counter() - t_weights_start)*1000:.2f}ms")

        # State
        self.cursor_loc = None

        self.painting = False
        self.world_radius = 0.1 
        
        self.is_blur = False
        self.is_harden = False
        self.is_navigating_radius = False
        self.is_navigating_strength = False
        self.nav_start_x = 0
        self.nav_start_val = 0.0
        self.mouse_x = 0
        self.mouse_y = 0
        self.prev_cursor_loc = None 
        
        # Undo & Perf
        self.undo_stack = []
        self.message_text = ""
        self.message_timer = 0
        self.last_compute_time = 0.0 
        self.debug_mode = self.debug_mode
        
        self.radius_px = context.scene.wynn_brush_radius
        self.strength = context.scene.wynn_brush_strength

        self.temp_group_sums = {}
        self.temp_new_weights = {}

        args = (self, context)
        self._handle_3d = bpy.types.SpaceView3D.draw_handler_add(draw_circles_callback, args, 'WINDOW', 'POST_VIEW')
        self._handle_2d = bpy.types.SpaceView3D.draw_handler_add(draw_text_callback, args, 'WINDOW', 'POST_PIXEL')

        self.update_header(context)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    
    # Removed flatten_weights helper (Logic moved to Invoke)

    def paint_stroke(self, context):
        if not self.cursor_loc: 
            # print("DEBUG: No Cursor Loc") 
            return
        
        # DEBUG: Verify we entered paint_stroke
        found = self.kd_visual.find_range(self.cursor_loc, self.world_radius)
        print(f"DEBUG: Stroke. Radius={self.world_radius:.4f} Found={len(found)} Blur={self.is_blur} DLL={self.dll is not None}")
        
        obj = self.mesh_object
        vertices = obj.data.vertices
        vertex_groups = obj.vertex_groups
        
        idx_active = obj.vertex_groups.active_index
        # ... Mirror/Smear logic ...
        
        if not found: return
        
        # --- C++ FAST PATH (Zero-Copy) ---
        has_new_api = hasattr(self.dll, 'apply_vertex_logic_strided') if self.dll else False
        use_cpp = self.dll is not None
        
        # Fallback if Paint mode but new API missing
        if not self.is_blur and not has_new_api:
            use_cpp = False

        if use_cpp:
            # TIMER START: PREP
            t0 = time.perf_counter()
            
            # Prepare Common Data
            base_factor = self.strength * 0.5 # For Blur (Legacy)
            
            # Prepare Lists
            # Max possible size = len(found) * 2
            max_targets = len(found) * 2
            target_indices = (ctypes.c_int * max_targets)()
            
            # For Paint/Harden we need factors
            if not self.is_blur:
               target_factors = (ctypes.c_float * max_targets)()
            
            count = 0
            
            # Pre-calc for Factors
            radius_sq = self.world_radius * self.world_radius
            inv_radius_sq = 1.0 / radius_sq if radius_sq > 0 else 0
            strength_factor = self.strength
            
            for (co, index, dist) in found:
                # Factor Calc
                dist_sq = dist * dist
                falloff = 1.0 - (dist_sq * inv_radius_sq)
                if falloff <= 0: continue
                
                current_factor = strength_factor * falloff
                
                # Add Primary
                target_indices[count] = index
                if not self.is_blur: target_factors[count] = current_factor
                count += 1
                

            
            if count == 0: return

            # TIMER START: CALC
            t1 = time.perf_counter()
            t_prep = (t1 - t0) * 1000.0

            # Dispatch
            if self.is_blur:
                 self.dll.smooth_strided(
                    self.c_adj_starts, self.c_adj_indices, self.c_adj_weights,
                    self.c_weight_indices, self.c_weight_values,
                    target_indices, count, base_factor
                )
            else:
                 # Paint (0) or Harden (1)
                 mode = 1 if self.is_harden else 0
                 
                 smear_val = -1.0
                 if mode == 0 and self.prev_cursor_loc:
                      smear_val = self.get_source_weight(obj, self.prev_cursor_loc, idx_active, method='NEAREST')
                 
                 self.dll.apply_vertex_logic_strided(
                    self.c_weight_indices, self.c_weight_values,
                    target_indices, target_factors,
                    count, idx_active, mode, smear_val
                 )
            
            # TIMER START: APPLY
            t2 = time.perf_counter()
            t_calc = (t2 - t1) * 1000.0

            # 3. Apply Back to Blender (Optimized)
            stride = self.c_stride
            ptr_indices = self.c_weight_indices
            ptr_values = self.c_weight_values
            
            for i in range(count):
                v_idx = target_indices[i]
                v = vertices[v_idx]
                
                base = v_idx * stride
                
                # Build Map of Desired State
                new_map = {}
                for k in range(stride):
                    g_idx = ptr_indices[base + k]
                    if g_idx < 0: continue 
                    val = ptr_values[base + k]
                    if val > 0.0001: new_map[g_idx] = val
                
                # Single Pass Update: Iterate existing groups once
                to_remove = []
                
                # Update existing & Mark for removal
                for g in v.groups:
                    g_id = g.group
                    if g_id in new_map:
                        # Update in-place (Fastest)
                        w = new_map[g_id]
                        if abs(g.weight - w) > 0.00001:
                            g.weight = w
                        # Remove from map so we know it's handled
                        del new_map[g_id]
                    else:
                        # Existing group not in new set -> Remove
                        to_remove.append(g_id)
                
                # Exec Removals
                for g_id in to_remove:
                    try: vertex_groups[g_id].remove([v_idx])
                    except RuntimeError: pass
                
                # Exec Adds (Remaining items in new_map are new groups)
                for g_id, val in new_map.items():
                    try: vertex_groups[g_id].add([v_idx], val, 'REPLACE')
                    except RuntimeError: pass
            
            obj.data.update()
            
            t3 = time.perf_counter()
            t_apply = (t3 - t2) * 1000.0
            
            print(f"[Core: C++] Prep: {t_prep:.2f}ms | Calc: {t_calc:.2f}ms | Apply: {t_apply:.2f}ms | Total: {(t_prep+t_calc+t_apply):.2f}ms")
            return

        # --- FALLBACK PYTHON ---
        print("[Core: Python] Fallback Used")
        did_update = False
        
        # Pre-calc constants
        radius_sq = self.world_radius * self.world_radius
        inv_radius_sq = 1.0 / radius_sq if radius_sq > 0 else 0
        strength_factor = self.strength
        
        for (co, index, dist) in found:
            v = vertices[index]
            
            # Quadratic Falloff: 1 - (dist^2 / rad^2)
            dist_sq = dist * dist
            falloff = 1.0 - (dist_sq * inv_radius_sq)
            if falloff <= 0: continue
            
            base_factor = strength_factor * falloff
            
            if self.is_blur:
                final_factor = base_factor * 0.5 
                self.smooth_vertex_all_groups(vertices, vertex_groups, v, final_factor)
                did_update = True
                

            else:
                final_factor = base_factor * 0.25 if self.is_harden else base_factor
                self.apply_logic(obj, v, idx_active, final_factor, smear_val=smear_src_val)
                did_update = True
                


        if did_update:
            obj.data.update()

    def refresh_geometry(self, context, obj):
        depsgraph = context.evaluated_depsgraph_get()
        eval_obj = obj.evaluated_get(depsgraph)
        temp_mesh = eval_obj.to_mesh()
        
        if len(temp_mesh.vertices) != len(obj.data.vertices):
            eval_obj.to_mesh_clear()
            return False

        # Optimization: Transform entire mesh to world space in C (much faster than Python loop)
        temp_mesh.transform(eval_obj.matrix_world)

        self.kd_visual = KDTree(len(temp_mesh.vertices))
        self.cached_coords = [None] * len(temp_mesh.vertices)
        kd_insert = self.kd_visual.insert
        
        for i, v in enumerate(temp_mesh.vertices):
            co = v.co
            kd_insert(co, i)
            self.cached_coords[i] = co
            
        self.kd_visual.balance()
        eval_obj.to_mesh_clear()
        return True

    def calculate_world_radius(self, context, location_3d):
        if not location_3d or not context.region_data: return 0.001
        region = context.region
        rv3d = context.region_data
        coord_2d = view3d_utils.location_3d_to_region_2d(region, rv3d, location_3d)
        if not coord_2d: return 0.001
        coord_2d_shifted = (coord_2d[0] + self.radius_px, coord_2d[1])
        loc_shifted = view3d_utils.region_2d_to_location_3d(region, rv3d, coord_2d_shifted, location_3d)
        return (loc_shifted - location_3d).length

    def save_undo_snapshot(self, obj):
        idx_active = obj.vertex_groups.active_index
        if idx_active == -1: return

        groups_to_save = {idx_active}

        
        snapshot = {}
        for g_idx in groups_to_save:
            weights = {}
            for v in obj.data.vertices:
                try:
                    found = False
                    for g in v.groups:
                        if g.group == g_idx:
                            weights[v.index] = g.weight
                            found = True
                            break
                    if not found:
                        weights[v.index] = 0.0
                except IndexError:
                    weights[v.index] = 0.0
            
            snapshot[g_idx] = weights
            
        self.undo_stack.append(snapshot)
        if len(self.undo_stack) > 20: 
            self.undo_stack.pop(0)

    def perform_undo(self, obj):
        if not self.undo_stack:
            self.show_message("Undo Stack Empty!")
            return

        self.show_message("Undo!")
        snapshot = self.undo_stack.pop()
        
        for g_idx, weights in snapshot.items():
            group = obj.vertex_groups[g_idx]
            for v_idx, w in weights.items():
                if w > 0.0001:
                    group.add([v_idx], w, 'REPLACE')
                else:
                    try:
                        group.remove([v_idx])
                    except RuntimeError: pass 
        obj.data.update()

    def show_message(self, text):
        self.message_text = text
        self.message_timer = 50 

    def modal(self, context, event):
        context.area.tag_redraw()
        if self.message_timer > 0: self.message_timer -= 1
        
        self.mouse_x = event.mouse_region_x
        self.mouse_y = event.mouse_region_y
        self.update_cursor(context, event)
        
        # Sync with Scene Properties (for Menu)
        if not self.is_navigating_radius:
            self.radius_px = context.scene.wynn_brush_radius
        else:
            context.scene.wynn_brush_radius = self.radius_px
            
        if not self.is_navigating_strength:
            self.strength = context.scene.wynn_brush_strength
        else:
            context.scene.wynn_brush_strength = self.strength

        # Undo
        if event.type == 'Z' and event.value == 'PRESS' and event.ctrl:
            self.perform_undo(context.active_object)
            return {'RUNNING_MODAL'}

        # Toggle Overlays (Shift + Alt + Z)
        if event.type == 'Z' and event.value == 'PRESS' and event.shift and event.alt:
            context.space_data.overlay.show_overlays = not context.space_data.overlay.show_overlays
            return {'RUNNING_MODAL'}

        # Navigation
        if self.is_navigating_radius:
            if event.type == 'MOUSEMOVE':
                diff = event.mouse_region_x - self.nav_start_x
                self.radius_px = int(max(1, self.nav_start_val + diff))
                return {'RUNNING_MODAL'}
            elif event.type in {'LEFTMOUSE', 'RET'}:
                self.is_navigating_radius = False
                return {'RUNNING_MODAL'}
            return {'RUNNING_MODAL'}

        if self.is_navigating_strength:
            if event.type == 'MOUSEMOVE':
                diff = event.mouse_region_x - self.nav_start_x
                self.strength = min(1.0, max(0.01, self.nav_start_val + (diff * 0.005)))
                return {'RUNNING_MODAL'}
            elif event.type in {'LEFTMOUSE', 'RET'}:
                self.is_navigating_strength = False
                return {'RUNNING_MODAL'}
            return {'RUNNING_MODAL'}


        
        if event.type == 'F' and event.value == 'PRESS':
            if event.shift:
                self.is_navigating_strength = True
                self.nav_start_x = event.mouse_region_x
                self.nav_start_val = self.strength
            else:
                self.is_navigating_radius = True
                self.nav_start_x = event.mouse_region_x
                self.nav_start_val = self.radius_px
            return {'RUNNING_MODAL'}

        self.is_blur = event.shift
        self.is_harden = event.ctrl
        
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
             return {'PASS_THROUGH'}

        # Allow Bone Transforms (G, R, S)
        if event.type in {'G', 'R', 'S'} and event.value == 'PRESS':
            return {'PASS_THROUGH'}

        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                # Start Painting
                if event.ctrl and event.shift:
                    return {'PASS_THROUGH'}

                self.refresh_geometry(context, self.mesh_object)
                self.save_undo_snapshot(self.mesh_object)
                self.painting = True
                self.prev_cursor_loc = self.cursor_loc
            elif event.value == 'RELEASE':
                self.painting = False
        
        if event.type == 'RIGHTMOUSE' and event.value == 'PRESS':
            bpy.ops.wm.call_menu(name="WYNN_MT_brush_context_menu")
            return {'RUNNING_MODAL'}
        
        if event.type == 'ESC':
            bpy.types.SpaceView3D.draw_handler_remove(self._handle_3d, 'WINDOW')
            bpy.types.SpaceView3D.draw_handler_remove(self._handle_2d, 'WINDOW')
            context.area.header_text_set(None)
            return {'FINISHED'}

        if self.painting:
            # --- START TIMER ---
            t0 = time.perf_counter()
            
            self.paint_stroke(context)
            
            # --- END TIMER ---
            t1 = time.perf_counter()
            self.last_compute_time = (t1 - t0) * 1000.0 # Convert to ms
            
            if self.cursor_loc:
                self.prev_cursor_loc = self.cursor_loc

        return {'RUNNING_MODAL'}

    def update_cursor(self, context, event):
        # Update Input State
        self.is_blur = event.shift
        
        if not context.region_data:
            self.cursor_loc = None
            return
        region = context.region
        rv3d = context.region_data
        coord = event.mouse_region_x, event.mouse_region_y
        try:
            ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
            view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
        except AttributeError:
            self.cursor_loc = None
            return
        hit, loc, _, _, _, _ = context.scene.ray_cast(context.view_layer.depsgraph, ray_origin, view_vector)
        if hit:
            self.cursor_loc = loc
            self.world_radius = self.calculate_world_radius(context, loc)

        else:
            self.cursor_loc = None


    def get_source_weight(self, obj, location, group_idx, method='NEAREST'):
        if not location: return -1.0
        if method == 'NEAREST':
            co, index, dist = self.kd_visual.find(location)
            v = obj.data.vertices[index]
            try:
                for g in v.groups:
                    if g.group == group_idx: return g.weight
            except IndexError: pass
            return 0.0
        else: 
            found = self.kd_visual.find_range(location, self.world_radius)
            if not found: return -1.0
            total = 0.0
            count = 0
            for (co, index, dist) in found:
                v = obj.data.vertices[index]
                val = 0.0
                try:
                    for g in v.groups:
                        if g.group == group_idx:
                            val = g.weight
                            break
                except IndexError: pass
                total += val
                count += 1
            if count == 0: return 0.0 
            return total / count

    # Optimized: Reuse buffers + Distance Weights + Max Influence Limit
    def smooth_vertex_all_groups(self, vertices, vertex_groups, vertex, factor):
        neighbors = self.adjacency.get(vertex.index)
        if not neighbors: return

        self.temp_group_sums.clear()
        
        # Track total weight for normalization of the average
        total_edge_weight = 0.0
        
        # 1. Accumulate Weighted Sums
        for n_idx, edge_w in neighbors:
            n_v = vertices[n_idx]
            total_edge_weight += edge_w
            
            for g in n_v.groups:
                self.temp_group_sums[g.group] = self.temp_group_sums.get(g.group, 0.0) + (g.weight * edge_w)
        
        if total_edge_weight <= 0.00001: return 
        inv_total_edge = 1.0 / total_edge_weight
            
        # 3. Blend
        self.temp_new_weights.clear()
        
        inv_factor = 1.0 - factor
        
        # Calculate Un-normalized New Weights
        # Step A: Process groups present in neighbors
        for g_idx, w_sum in self.temp_group_sums.items():
            avg_w = w_sum * inv_total_edge
            
            # Find current weight
            cur_w = 0.0
            for g in vertex.groups:
                if g.group == g_idx:
                    cur_w = g.weight
                    break
            
            new_w = (cur_w * inv_factor) + (avg_w * factor)
            if new_w > 0.0001:
                self.temp_new_weights[g_idx] = new_w
        
        # Step B: Process groups present in Self but NOT in Neighbors
        for g in vertex.groups:
            if g.group not in self.temp_new_weights:
                new_w = g.weight * inv_factor
                if new_w > 0.0001:
                    self.temp_new_weights[g.group] = new_w

        # --- MAX INFLUENCE LIMIT & NORMALIZATION ---
        
        sorted_weights = sorted(self.temp_new_weights.items(), key=lambda x: x[1], reverse=True)
        
        MAX_INFLUENCE = 4
        final_list = sorted_weights[:MAX_INFLUENCE]
        
        total_final = sum(pair[1] for pair in final_list)
        
        if total_final > 0.00001:
            ratio = 1.0 / total_final
            
            # Apply Changes
            # 1. Update/Add kept groups
            kept_indices = []
            for g_idx, raw_w in final_list:
                kept_indices.append(g_idx)
                final_w = raw_w * ratio
                
                exists = False
                for g in vertex.groups:
                    if g.group == g_idx:
                        g.weight = final_w
                        exists = True
                        break
                
                if not exists:
                    vertex_groups[g_idx].add([vertex.index], final_w, 'REPLACE')
            
            # 2. Remove culled groups
            to_remove = []
            for g in vertex.groups:
                if g.group not in kept_indices:
                    to_remove.append(g.group)
            
            for g_idx in to_remove:
                vertex_groups[g_idx].remove([vertex.index])
                
    def update_header(self, context):
        context.area.header_text_set(f"F: Size | Shift+F: Strength | D: Debug | Undo: {len(self.undo_stack)} | Perf: {self.last_compute_time:.2f}ms")

def register():
    bpy.types.Scene.wynn_brush_radius = bpy.props.IntProperty(name="Radius (Px)", default=50, min=1, max=1000)
    bpy.types.Scene.wynn_brush_strength = bpy.props.FloatProperty(name="Strength", default=0.5, min=0.01, max=1.0)
    bpy.utils.register_class(WYNN_MT_brush_context_menu)
    bpy.utils.register_class(WYNN_OT_smear_perf_monitor)
def unregister():
    del bpy.types.Scene.wynn_brush_radius
    del bpy.types.Scene.wynn_brush_strength
    bpy.utils.unregister_class(WYNN_MT_brush_context_menu)
    bpy.utils.unregister_class(WYNN_OT_smear_perf_monitor)
if __name__ == "__main__":
    register()