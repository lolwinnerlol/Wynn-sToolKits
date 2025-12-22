import bpy
import gpu
import blf
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from mathutils.kdtree import KDTree
from bpy_extras import view3d_utils
import math
import time  # NEW: For performance timing

# --- UTILS ---
def flip_name(name):
    if name.endswith('.L'): return name[:-2] + '.R'
    if name.endswith('.R'): return name[:-2] + '.L'
    if name.endswith('_L'): return name[:-2] + '_R'
    if name.endswith('_R'): return name[:-2] + '_L'
    if 'Left' in name: return name.replace('Left', 'Right')
    if 'Right' in name: return name.replace('Right', 'Left')
    return name 

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
    
    # 4. INFO (Mirror + Undo)
    blf.position(font_id, x, y - 25, 0)
    blf.color(font_id, 0.8, 0.8, 0.8, 1)
    sym_text = "ON" if self.use_symmetry else "OFF"
    debug_text = "ON" if self.debug_mode else "OFF"
    blf.draw(font_id, f"Mirror: {sym_text} | Undo: {len(self.undo_stack)} | Debug(D): {debug_text}")

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
    
    if self.use_symmetry and self.mirror_loc_visual and not (self.is_navigating_radius or self.is_navigating_strength):
        coords_blue = get_circle(self.mirror_loc_visual, self.world_radius)
        if coords_blue:
            batch_blue = batch_for_shader(shader, 'LINE_STRIP', {"pos": coords_blue})
            shader.uniform_float("color", (0.2, 0.6, 1.0, 1.0))
            batch_blue.draw(shader)

    gpu.state.line_width_set(1.0)
    gpu.state.blend_set('NONE')

class WYNN_OT_smear_perf_monitor(bpy.types.Operator):
    """Hard Smear + Performance Monitor"""
    bl_idname = "wynn.smear_perf_monitor"
    bl_label = "Smear (Perf Monitor)"
    bl_options = {'REGISTER', 'UNDO'}

    radius_px: bpy.props.IntProperty(name="Radius (Px)", default=50, min=1, max=1000)
    strength: bpy.props.FloatProperty(name="Strength", default=0.5, min=0.01, max=1.0)
    use_symmetry: bpy.props.BoolProperty(name="X Mirror", default=True)
    debug_mode: bpy.props.BoolProperty(name="Debug Mode", default=False)

    def invoke(self, context, event):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Select a Mesh")
            return {'CANCELLED'}

        # 1. MAP
        self.vert_map = {} 
        kd_rest = KDTree(len(obj.data.vertices))
        for i, v in enumerate(obj.data.vertices):
            kd_rest.insert(v.co, i)
        kd_rest.balance()
        for i, v in enumerate(obj.data.vertices):
            if i in self.vert_map: continue
            target = v.co.copy()
            target.x *= -1
            co, index, dist = kd_rest.find(target)
            if dist < 0.002: 
                self.vert_map[i] = index
                self.vert_map[index] = i
            else:
                self.vert_map[i] = None 

        # 2. CACHE
        depsgraph = context.evaluated_depsgraph_get()
        eval_obj = obj.evaluated_get(depsgraph)
        temp_mesh = eval_obj.to_mesh()
        if len(temp_mesh.vertices) != len(obj.data.vertices):
            eval_obj.to_mesh_clear()
            self.report({'ERROR'}, "Vertex mismatch")
            return {'CANCELLED'}

        self.kd_visual = KDTree(len(temp_mesh.vertices))
        self.cached_coords = []
        world_mat = eval_obj.matrix_world
        for i, v in enumerate(temp_mesh.vertices):
            world_pos = world_mat @ v.co
            self.kd_visual.insert(world_pos, i)
            self.cached_coords.append(world_pos)
        self.kd_visual.balance()
        eval_obj.to_mesh_clear()

        # 3. ADJACENCY (Topology)
        self.adjacency = {}
        for edge in obj.data.edges:
            v1, v2 = edge.vertices
            self.adjacency.setdefault(v1, []).append(v2)
            self.adjacency.setdefault(v2, []).append(v1)

        # State
        self.cursor_loc = None
        self.mirror_loc_visual = None
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
        self.last_compute_time = 0.0 # Performance Tracking
        self.debug_mode = self.debug_mode # Initialize from property

        args = (self, context)
        self._handle_3d = bpy.types.SpaceView3D.draw_handler_add(draw_circles_callback, args, 'WINDOW', 'POST_VIEW')
        self._handle_2d = bpy.types.SpaceView3D.draw_handler_add(draw_text_callback, args, 'WINDOW', 'POST_PIXEL')

        self.update_header(context)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

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
        if self.use_symmetry:
            name_active = obj.vertex_groups[idx_active].name
            idx_mirror = obj.vertex_groups.find(flip_name(name_active))
            if idx_mirror != -1:
                groups_to_save.add(idx_mirror)
        
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

        # Undo
        if event.type == 'Z' and event.value == 'PRESS' and event.ctrl:
            self.perform_undo(context.active_object)
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

        if event.type == 'X' and event.value == 'PRESS':
            self.use_symmetry = not self.use_symmetry
            self.update_header(context)
            return {'RUNNING_MODAL'}
        
        if event.type == 'D' and event.value == 'PRESS':
            self.debug_mode = not self.debug_mode
            self.show_message(f"Debug Mode: {'ON' if self.debug_mode else 'OFF'}")
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

        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                self.save_undo_snapshot(context.active_object)
                self.painting = True
                self.prev_cursor_loc = self.cursor_loc
            elif event.value == 'RELEASE':
                self.painting = False
        
        if event.type in {'ESC', 'RIGHTMOUSE'}:
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
            if self.use_symmetry and not (self.is_navigating_radius or self.is_navigating_strength):
                co, index, dist = self.kd_visual.find(loc)
                mirror_idx = self.vert_map.get(index)
                if mirror_idx is not None:
                    self.mirror_loc_visual = self.cached_coords[mirror_idx]
                else:
                    self.mirror_loc_visual = None
        else:
            self.cursor_loc = None
            self.mirror_loc_visual = None

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

    def paint_stroke(self, context):
        if not self.cursor_loc: return
        obj = context.active_object
        
        idx_active = obj.vertex_groups.active_index
        if idx_active == -1: return
        name_active = obj.vertex_groups[idx_active].name
        
        idx_mirror = obj.vertex_groups.find(flip_name(name_active))
        if idx_mirror == -1: idx_mirror = idx_active 

        found = self.kd_visual.find_range(self.cursor_loc, self.world_radius)
        
        smear_src_val = -1.0
        smear_src_val_mirror = -1.0
        blur_avg = 0.0
        blur_avg_mirror = 0.0
        
        if not self.is_blur and not self.is_harden:
            if self.prev_cursor_loc:
                smear_src_val = self.get_source_weight(obj, self.prev_cursor_loc, idx_active, method='NEAREST')
                if self.use_symmetry and self.mirror_loc_visual:
                    smear_src_val_mirror = self.get_source_weight(obj, self.mirror_loc_visual, idx_mirror, method='NEAREST')
        
        did_update = False
        for (co, index, dist) in found:
            v = obj.data.vertices[index]
            norm_dist = dist / self.world_radius
            falloff = 1.0 - (norm_dist * norm_dist)
            final_factor = self.strength * max(0.0, falloff)
            
            # Topological Smooth (Laplacian)
            if self.is_blur:
                neighbors = self.adjacency.get(index, [])
                if neighbors:
                    total_w = 0.0
                    for n_idx in neighbors:
                        w = 0.0
                        try:
                            for g in obj.data.vertices[n_idx].groups:
                                if g.group == idx_active:
                                    w = g.weight
                                    break
                        except IndexError: pass
                        total_w += w
                    blur_avg = total_w / len(neighbors)
                else:
                    blur_avg = 0.0

            self.apply_logic(obj, v, idx_active, final_factor, 
                             smear_val=smear_src_val, blur_avg=blur_avg)
            did_update = True
            
            if self.use_symmetry:
                m_idx = self.vert_map.get(index)
                if m_idx is not None and m_idx != index:
                    v_m = obj.data.vertices[m_idx]
                    
                    if self.is_blur:
                        neighbors_m = self.adjacency.get(m_idx, [])
                        if neighbors_m:
                            total_w_m = 0.0
                            for n_idx_m in neighbors_m:
                                w_m = 0.0
                                try:
                                    for g in obj.data.vertices[n_idx_m].groups:
                                        if g.group == idx_mirror:
                                            w_m = g.weight
                                            break
                                except IndexError: pass
                                total_w_m += w_m
                            blur_avg_mirror = total_w_m / len(neighbors_m)
                        else:
                            blur_avg_mirror = 0.0

                    self.apply_logic(obj, v_m, idx_mirror, final_factor, 
                                     smear_val=smear_src_val_mirror, blur_avg=blur_avg_mirror)

        if did_update:
            obj.data.update()

    def normalize_vertex(self, vertex, main_group_index):
        total = 0.0
        for g in vertex.groups:
            total += g.weight
        main_weight = 0.0
        for g in vertex.groups:
            if g.group == main_group_index:
                main_weight = g.weight
                break
        if abs(total - 1.0) < 0.001: return

        remaining_allowance = 1.0 - main_weight
        if remaining_allowance < 0: remaining_allowance = 0
        sum_others = total - main_weight
        
        if sum_others <= 0.0001:
            if main_weight > 1.0:
                for g in vertex.groups:
                    if g.group == main_group_index: g.weight = 1.0
            return

        ratio = remaining_allowance / sum_others
        for g in vertex.groups:
            if g.group != main_group_index:
                g.weight *= ratio

    def apply_logic(self, obj, vertex, group_idx, factor, smear_val=-1, blur_avg=0):
        current_w = 0.0
        try:
            for g in vertex.groups:
                if g.group == group_idx:
                    current_w = g.weight
                    break
        except IndexError: pass
        
        new_w = current_w
        if self.is_harden:
            new_w = get_harden_target(current_w, factor)
            if self.debug_mode:
                target = 1.0 if current_w >= 0.5 else 0.0
                print(f"[HARDEN] v_idx:{vertex.index}, cur:{current_w:.3f}, target:{target:.1f}, factor:{factor:.3f} -> new:{new_w:.3f}")
        elif self.is_blur:
            new_w = get_smooth_target(current_w, blur_avg, factor)
            if self.debug_mode:
                print(f"[BLUR] v_idx:{vertex.index}, cur:{current_w:.3f}, avg:{blur_avg:.3f}, factor:{factor:.3f} -> new:{new_w:.3f}")
        else:
            if smear_val >= 0:
                new_w = current_w + (smear_val - current_w) * factor
                if self.debug_mode:
                    print(f"[SMEAR] v_idx:{vertex.index}, cur:{current_w:.3f}, src:{smear_val:.3f}, factor:{factor:.3f} -> new:{new_w:.3f}")

        if new_w != current_w:
            in_group = False
            try:
                for g in vertex.groups:
                    if g.group == group_idx:
                        g.weight = new_w
                        in_group = True
                        break
            except IndexError: pass
            
            if not in_group and new_w > 0.001:
                obj.vertex_groups[group_idx].add([vertex.index], new_w, 'REPLACE')
            self.normalize_vertex(vertex, group_idx)

    def update_header(self, context):
        sym_str = "ON" if self.use_symmetry else "OFF"
        context.area.header_text_set(f"F: Size | Shift+F: Strength | X: Mirror ({sym_str}) | D: Debug | Undo: {len(self.undo_stack)} | Perf: {self.last_compute_time:.2f}ms")

def register():
    bpy.utils.register_class(WYNN_OT_smear_perf_monitor)
def unregister():
    bpy.utils.unregister_class(WYNN_OT_smear_perf_monitor)
if __name__ == "__main__":
    register()