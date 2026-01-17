import bpy
import gpu
import gpu_extras.batch
import colorsys
from bpy.props import BoolProperty, IntProperty, FloatVectorProperty, StringProperty, CollectionProperty, PointerProperty, FloatProperty

# Global Cache for Onion Skin Batches
# Structure: ONION_SKIN_CACHE[object_name][frame] = batch
# Structure: ONION_SKIN_KEYFRAMES[object_name] = {frame: is_constant_bool}
ONION_SKIN_KEYFRAMES = {} 
ONION_SKIN_CACHE = {}
_onion_draw_handle = None

# -------------------------------------------------------------------
#   Data Structures
# -------------------------------------------------------------------

from .groups import OnionSkinGroup

class OnionSkinSettings(bpy.types.PropertyGroup):
    """Global Onion Skin Settings attached to Scene"""
    def update_onion_skin_enabled(self, context):
        """Show warning popup when enabled"""
        if self.is_enabled:
            def draw_popup(popup, context):
                popup.layout.label(text="Onion Skin ตอนนี้ไม่เสถียรขอให้ใช้อย่างระมัดระวังน้าา")
            context.window_manager.popup_menu(draw_popup, title="Warning", icon='ERROR')

    is_enabled: BoolProperty(name="Enable Onion Skin", default=False, update=update_onion_skin_enabled)
    
    # We rename "Before" to "Ghosts Before" or just keep context clear
    frame_before: IntProperty(name="Before", default=1, min=0)
    frame_after: IntProperty(name="After", default=1, min=0)
    
    color_before: FloatVectorProperty(
        name="Color Before", subtype='COLOR', default=(1.0, 0.0, 0.0), min=0.0, max=1.0
    )
    color_after: FloatVectorProperty(
        name="Color After", subtype='COLOR', default=(0.0, 1.0, 0.0), min=0.0, max=1.0
    )
    
    # Removed: step, use_keyframe_only
    
    opacity: FloatProperty(name="Opacity", default=0.05, min=0.0, max=1.0)
    
    use_silhouette_group: BoolProperty(
        name="Silhouette Uses Group",
        default=False,
        description="If enabled, the Silhouette tool will only show objects in the active Onion Skin Group"
    )
    
    groups: CollectionProperty(type=OnionSkinGroup)
    
    def update_active_group(self, context):
        """Callback for when active group changes"""
        from . import silhouette
        
        # Check if Silhouette is active
        stored_props = getattr(context.window_manager, "wynn_animator_props", None)
        if stored_props and stored_props.is_silhouette_active:
             silhouette.update_silhouette_visibility(context)

    active_group_index: IntProperty(
        update=update_active_group
    )

# -------------------------------------------------------------------
#   Operators
# -------------------------------------------------------------------

def get_keyframe_data(obj):
    """
    Returns dict {frame: is_constant(bool)}
    is_constant is True if ALL channels at this frame are CONSTANT.
    If ANY channel is Bezier/Linear, we consider it 'Moving' (is_constant=False).
    """
    
    def find_action(target):
        if target.animation_data and target.animation_data.action:
            return target.animation_data.action
        if target.parent:
            return find_action(target.parent)
        return None

    action = find_action(obj)
    
    if not action:
        return {}
        
    # Default Assume True (Constant) until proven otherwise (Bezier/Linear)
    # If a frame is never seen, it's not in the dict.
    keyframe_data = {} 
    
    def process_fcurves(fcurves_collection):
        if not fcurves_collection: return
        for fcurve in fcurves_collection:
            for kp in fcurve.keyframe_points:
                frame = int(kp.co.x)
                is_const = (kp.interpolation == 'CONSTANT')
                
                if frame not in keyframe_data:
                    keyframe_data[frame] = is_const
                else:
                    # If already marked False (Moving), stays False.
                    # If currently True (Constant), but this one is False -> Mark False.
                    if keyframe_data[frame] and not is_const:
                        keyframe_data[frame] = False

    if hasattr(action, "fcurves"):
        process_fcurves(action.fcurves)
    elif hasattr(action, "layers"):
        for i, layer in enumerate(action.layers):
            if hasattr(layer, "strips"):
                for j, strip in enumerate(layer.strips):
                    if hasattr(strip, "fcurves"):
                        process_fcurves(strip.fcurves)
                    if hasattr(strip, "channelbags"):
                        for k, bag in enumerate(strip.channelbags):
                            if hasattr(bag, "fcurves"):
                                process_fcurves(bag.fcurves)
                            elif hasattr(bag, "channels"):
                                process_fcurves(bag.channels)
                    elif hasattr(strip, "channelbag"):
                         bag = strip.channelbag
                         if hasattr(bag, "fcurves"):
                             process_fcurves(bag.fcurves)
    elif hasattr(action, "curves"):
         process_fcurves(action.curves)
         
    return keyframe_data

class WYNN_OT_update_onion_skin(bpy.types.Operator):
    """Bake all keyframes for onion skinning"""
    bl_idname = "wynn.update_onion_skin"
    bl_label = "Bake All Keyframes"
    
    def execute(self, context):
        global ONION_SKIN_CACHE, ONION_SKIN_KEYFRAMES
        # Do not clear global cache, allowing multi-group builds if desired
        # ONION_SKIN_CACHE = {} 
        # ONION_SKIN_KEYFRAMES = {}
        
        settings = context.scene.wynn_onion
        if not settings.is_enabled:
            return {'CANCELLED'}
        
        # Ensure Active Group
        if not settings.groups or settings.active_group_index >= len(settings.groups):
            return {'FINISHED'}
            
        active_group = settings.groups[settings.active_group_index]
        
        scene = context.scene
        saved_frame = scene.frame_current
        
        # Collect Objects from Active Group Only
        objects_to_cache = set()
        for item in active_group.objects:
            if item.obj:
                objects_to_cache.add(item.obj)
        
        if not objects_to_cache:
            return {'FINISHED'}
            
        # Clear existing cache for these specific objects to ensure fresh bake
        for obj in objects_to_cache:
            ONION_SKIN_CACHE[obj.name] = {}
            ONION_SKIN_KEYFRAMES[obj.name] = {}

        # Calculate ALL Frames to Cache across all objects in this group
        total_frames_to_cache = set()
        
        for obj in objects_to_cache:
            # key_data is {frame: is_constant}
            key_data = get_keyframe_data(obj)
            ONION_SKIN_KEYFRAMES[obj.name] = key_data
            total_frames_to_cache.update(key_data.keys())
            
        sorted_frames_to_cache = sorted(list(total_frames_to_cache))
        
        print(f"Onion Skin: Baking {len(sorted_frames_to_cache)} frames for group '{active_group.name}'...")
        
        # Bake
        try:
            for frame in sorted_frames_to_cache:
                scene.frame_set(frame)
                context.view_layer.update() 
                
                for obj in objects_to_cache:
                    obj_keys = ONION_SKIN_KEYFRAMES.get(obj.name, {})
                    if frame not in obj_keys: 
                        continue

                    if obj.name not in ONION_SKIN_CACHE:
                        ONION_SKIN_CACHE[obj.name] = {}
                        
                    try:
                        eval_obj = obj.evaluated_get(context.evaluated_depsgraph_get())
                        mesh = eval_obj.to_mesh()
                        
                        matrix_world = eval_obj.matrix_world
                        coords = [matrix_world @ v.co for v in mesh.vertices]
                        
                        mesh.calc_loop_triangles()
                        indices = []
                        for tri in mesh.loop_triangles:
                            indices.append((tri.vertices[0], tri.vertices[1], tri.vertices[2]))
                        
                        if coords and indices:
                            batch = gpu_extras.batch.batch_for_shader(
                                gpu.shader.from_builtin('UNIFORM_COLOR'),
                                'TRIS',
                                {"pos": coords},
                                indices=indices
                            )
                            ONION_SKIN_CACHE[obj.name][frame] = batch
                        
                        eval_obj.to_mesh_clear()
                        
                    except Exception as e:
                        print(f"Error caching {obj.name} at {frame}: {e}")
                        
        finally:
            scene.frame_set(saved_frame)
            
        return {'FINISHED'}

# -------------------------------------------------------------------
#   Registration
# -------------------------------------------------------------------

classes = (
    OnionSkinSettings,
    WYNN_OT_update_onion_skin,
)

# -------------------------------------------------------------------
#   Draw Handler
# -------------------------------------------------------------------

def get_faded_color(base_rgb, base_alpha, index, total, is_before=True):
    """Calculates color with falloff for saturation, value, and alpha"""
    # index: For 'before', 0 is furthest, total-1 is closest to current frame
    #        For 'after', 0 is closest, total-1 is furthest
    
    if total <= 1:
        t = 0.0
    else:
        if is_before:
            # We want t=0 at closest (index=total-1), t=1 at furthest (index=0)
            t = (total - 1 - index) / (total - 1)
        else:
            # We want t=0 at closest (index=0), t=1 at furthest (index=total-1)
            t = index / (total - 1)
            
    h, s, v = colorsys.rgb_to_hsv(*base_rgb)
    
    # Falloff Settings
    # Further away (t -> 1.0) = Less Saturation, Less Value (darker/greyer)
    new_s = max(0.0, s * (1.0 - 0.6 * t))  # Drop sat by up to 60%
    new_v = max(0.0, v * (1.0 - 0.4 * t))  # Drop value by up to 40%
    
    r, g, b = colorsys.hsv_to_rgb(h, new_s, new_v)
    
    # Alpha Falloff
    # Furthest ghost fades significantly
    # e.g. fade down to 20% of base alpha
    new_a = base_alpha * (1.0 - 0.8 * t) 
    
    return (r, g, b, new_a)

def draw_onion_skins():
    context = bpy.context
    settings = context.scene.wynn_onion
    
    if not settings.is_enabled:
        return
        
    # Active Group Only Logic
    if not settings.groups or settings.active_group_index >= len(settings.groups):
        return

    active_group = settings.groups[settings.active_group_index]
    
    current_frame = context.scene.frame_current
    try:
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    except:
        shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
        
    shader.bind()
    
    gpu.state.blend_set('ALPHA')
    gpu.state.depth_test_set('NONE')
    
    try:
        # Only Draw Active Group
        for item in active_group.objects:
            obj = item.obj
            if not obj: continue
            if obj.name not in ONION_SKIN_CACHE: continue
            
            cached_frames_dict = ONION_SKIN_CACHE[obj.name]
            # obj_keys_dict is {frame: is_constant}
            obj_keys_dict = ONION_SKIN_KEYFRAMES.get(obj.name, {})
            sorted_keys = sorted(obj_keys_dict.keys())
            
            # Filter for Before
            before_keys = [k for k in sorted_keys if k < current_frame]
            
            # Intelligent Step Hiding Lookahead
            if before_keys:
                last_key = before_keys[-1]
                is_const = obj_keys_dict.get(last_key, False)
                if is_const:
                    before_keys.pop(-1)

            target_before = before_keys[-settings.frame_before:] if settings.frame_before > 0 else []
            
            # Filter for After
            after_keys = [k for k in sorted_keys if k > current_frame]
            target_after = after_keys[:settings.frame_after] if settings.frame_after > 0 else []
            
            # Draw Before
            total_before = len(target_before)
            for i, frame in enumerate(target_before):
                if frame in cached_frames_dict:
                    batch = cached_frames_dict[frame]
                    
                    col = get_faded_color(settings.color_before, settings.opacity, i, total_before, is_before=True)
                    shader.uniform_float("color", col)
                    batch.draw(shader)
                    
            # Draw After
            total_after = len(target_after)
            for i, frame in enumerate(target_after):
                    if frame in cached_frames_dict:
                        batch = cached_frames_dict[frame]
                        
                        col = get_faded_color(settings.color_after, settings.opacity, i, total_after, is_before=False)
                        shader.uniform_float("color", col)
                        batch.draw(shader)

    except Exception as e:
        pass 
        
    finally:
        gpu.state.blend_set('NONE')
        gpu.state.depth_test_set('LESS_EQUAL')


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
        
    bpy.types.Scene.wynn_onion = PointerProperty(type=OnionSkinSettings)
    
    global _onion_draw_handle
    if _onion_draw_handle is None:
        _onion_draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            draw_onion_skins, (), 'WINDOW', 'POST_VIEW'
        )

def unregister():
    del bpy.types.Scene.wynn_onion
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
        
    global _onion_draw_handle
    if _onion_draw_handle:
        bpy.types.SpaceView3D.draw_handler_remove(_onion_draw_handle, 'WINDOW')
        _onion_draw_handle = None

# -------------------------------------------------------------------
#   UI Drawing (to be called from main panel)
# -------------------------------------------------------------------

def draw_onion_skin_ui(layout, context):
    settings = context.scene.wynn_onion
    
    # Header / Master Toggle
    row = layout.row()
    
    toggle_text = "Disable" if settings.is_enabled else "Enable"
    toggle_icon = 'GHOST_ENABLED' if settings.is_enabled else 'GHOST_DISABLED'
    
    row.prop(settings, "is_enabled", text=toggle_text, icon=toggle_icon, toggle=True)
    
    # Dirty / Empty Check
    is_dirty = False
    is_empty = True
    
    if settings.groups and settings.active_group_index < len(settings.groups):
        active_group = settings.groups[settings.active_group_index]
        for item in active_group.objects:
            obj = item.obj
            if not obj: continue
            
            # Check Cache
            if obj.name in ONION_SKIN_CACHE and ONION_SKIN_CACHE[obj.name]:
                is_empty = False
                
                # Check Dirty (Simple Key Count Mismatch)
                # Performance Note: get_keyframe_data scans fcurves. 
                # Doing this every draw might be heavy for massive scenes.
                # For typical character rigs it is okay.
                cached_keys = ONION_SKIN_KEYFRAMES.get(obj.name, {})
                current_keys = get_keyframe_data(obj)
                
                # Compare keys (Frames only for seed)
                if set(cached_keys.keys()) != set(current_keys.keys()):
                    is_dirty = True
                    break # One dirty object is enough to warn
            else:
                 pass # Still empty
                 
    if settings.is_enabled:
        # Button Label
        btn_text = "Bake All Keyframes"
        btn_icon = 'FILE_REFRESH'
        
        if is_empty:
            layout.alert = True
            layout.label(text="No Cache Found!", icon='ERROR')
            btn_text = "Bake Onion Skin"
        elif is_dirty:
            layout.alert = True
            layout.label(text="Keyframes Changed!", icon='INFO')
            btn_text = "Re-Bake Changes"
            
        row.operator("wynn.update_onion_skin", text=btn_text, icon=btn_icon)
        layout.alert = False # Reset
    
    if not settings.is_enabled:
        pass
        
    box = layout.box()
    box.label(text="Settings")
    
    # Frame Before/After
    col = box.column(align=True)
    
    # Before
    row = col.row(align=True)
    split = row.split(factor=0.85, align=False)
    split.prop(settings, "frame_before", text="Before")
    split.prop(settings, "color_before", text="")
    
    # After
    row = col.row(align=True)
    split = row.split(factor=0.85, align=False)
    split.prop(settings, "frame_after", text="After")
    split.prop(settings, "color_after", text="")
    
    box.prop(settings, "opacity", slider=True)
