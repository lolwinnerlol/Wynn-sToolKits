import bpy
import gpu
import gpu_extras.batch
from bpy.props import BoolProperty, IntProperty, FloatVectorProperty, StringProperty, CollectionProperty, PointerProperty, FloatProperty

# Global Cache for Onion Skin Batches
# Structure: ONION_SKIN_CACHE[object_name][frame] = batch
ONION_SKIN_CACHE = {}
_onion_draw_handle = None

# -------------------------------------------------------------------
#   Data Structures
# -------------------------------------------------------------------

class OnionSkinObjectItem(bpy.types.PropertyGroup):
    """Reference to an object within a group"""
    obj: PointerProperty(type=bpy.types.Object, name="Object")

class OnionSkinGroup(bpy.types.PropertyGroup):
    """A logical group of objects for onion skinning"""
    name: StringProperty(name="Group Name", default="Group")
    is_active: BoolProperty(name="Active", default=True, description="Enable/Disable this group")
    
    objects: CollectionProperty(type=OnionSkinObjectItem)
    active_object_index: IntProperty()

class OnionSkinSettings(bpy.types.PropertyGroup):
    """Global Onion Skin Settings attached to Scene"""
    is_enabled: BoolProperty(name="Enable Onion Skin", default=False)
    
    frame_before: IntProperty(name="Before", default=1, min=0)
    frame_after: IntProperty(name="After", default=1, min=0)
    
    color_before: FloatVectorProperty(
        name="Color Before", subtype='COLOR', default=(1.0, 0.0, 0.0), min=0.0, max=1.0
    )
    color_after: FloatVectorProperty(
        name="Color After", subtype='COLOR', default=(0.0, 1.0, 0.0), min=0.0, max=1.0
    )
    
    step: IntProperty(name="Step", default=1, min=1, description="Frame step between ghosts")
    opacity: FloatProperty(name="Opacity", default=0.5, min=0.0, max=1.0)
    
    use_keyframe_only: BoolProperty(
        name="Keyframes Only", 
        default=False,
        description="Only show ghosts on frames that have keyframes (Animation Data)"
    )

    use_silhouette_group: BoolProperty(
        name="Silhouette Uses Group",
        default=False,
        description="If enabled, the Silhouette tool will only show objects in the active Onion Skin Group"
    )
    
    groups: CollectionProperty(type=OnionSkinGroup)
    
    def update_active_group(self, context):
        """Callback for when active group changes"""
        # We need to import inside to avoid circular imports during registration if possible,
        # or rely on module being loaded.
        # But top-level import is safer if cycles aren't an issue.
        # 'onion_skin' imports 'silhouette' ? No, 'silhouette' doesn't import 'onion_skin'.
        # Wait, 'silhouette' code references 'wynn_onion' which is defined here but accessed via scene.
        # So it's runtime dependency.
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

def get_nearby_keyframes(obj, current_frame, count_before, count_after):
    """Returns sorted lists of unique keyframe points (before, after)"""
    
    # Helper to find action on object or parents
    def find_action(target):
        if target.animation_data and target.animation_data.action:
            return target.animation_data.action
        if target.parent:
            return find_action(target.parent)
        return None

    action = find_action(obj)
    
    if not action:
        print(f"DEBUG: No Action found for {obj.name} (checked parents)")
        return [], []
        
    print(f"DEBUG: Found Action '{action.name}' for {obj.name}")
        
    print(f"DEBUG: Found Action '{action.name}' for {obj.name}")
        
    keyframes = set()
    
    # helper to process a collection of fcurves
    def collect_keys_from_fcurves(fcurves_collection):
        if not fcurves_collection: return
        for fcurve in fcurves_collection:
            for kp in fcurve.keyframe_points:
                keyframes.add(int(kp.co.x))

    # Try Legacy / Standard API
    if hasattr(action, "fcurves"):
        collect_keys_from_fcurves(action.fcurves)
        
    # Try New "Animation Next" / Slotted Action API (Layers -> Strips -> FCurves)
    elif hasattr(action, "layers"):
        print(f"DEBUG: Inspecting Layers for {action.name}...")
        # Iterate all layers
        for i, layer in enumerate(action.layers):
            if hasattr(layer, "strips"):
                for j, strip in enumerate(layer.strips):
                    # Check for FCurves directly on strip (unlikely based on logs)
                    if hasattr(strip, "fcurves"):
                        collect_keys_from_fcurves(strip.fcurves)
                    
                    # Check Channel Bags (New API confirmed by logs)
                    if hasattr(strip, "channelbags"):
                        for k, bag in enumerate(strip.channelbags):
                            # print(f"DEBUG: Bag {k} attributes: {[d for d in dir(bag) if not d.startswith('__')]}")
                            if hasattr(bag, "fcurves"):
                                collect_keys_from_fcurves(bag.fcurves)
                            elif hasattr(bag, "channels"):
                                collect_keys_from_fcurves(bag.channels)
                    
                    # Fallback for singular bag
                    elif hasattr(strip, "channelbag"):
                         bag = strip.channelbag
                         if hasattr(bag, "fcurves"):
                             collect_keys_from_fcurves(bag.fcurves)

    # Try 'curves' (Generic fallback if API renamed)
    elif hasattr(action, "curves"):
         collect_keys_from_fcurves(action.curves)
         
    # Fallback/Debug
    if not keyframes:
        print(f"DEBUG: Action '{action.name}' structure still seemingly empty. Keyframes set: {keyframes}")
            
    sorted_keys = sorted(list(keyframes))
    print(f"DEBUG: Found keys for {obj.name}: {sorted_keys}")
    
    # Filter
    before = [k for k in sorted_keys if k < current_frame]
    after = [k for k in sorted_keys if k > current_frame]
    
    # Get closest ones
    # slice takes the last N elements for 'before'
    before_slice = before[-count_before:] if count_before > 0 else []
    
    # slice takes first N elements for 'after'
    after_slice = after[:count_after] if count_after > 0 else []
    
    # print(f"DEBUG: Filtered for {obj.name} (Current {current_frame}): Before={before_slice}, After={after_slice}")
    
    return before_slice, after_slice

class WYNN_OT_add_onion_group(bpy.types.Operator):
    """Add a new object group"""
    bl_idname = "wynn.add_onion_group"
    bl_label = "Add Group"
    
    def execute(self, context):
        settings = context.scene.wynn_onion
        group = settings.groups.add()
        group.name = f"Group {len(settings.groups)}"
        settings.active_group_index = len(settings.groups) - 1
        return {'FINISHED'}

class WYNN_OT_remove_onion_group(bpy.types.Operator):
    """Remove the active object group"""
    bl_idname = "wynn.remove_onion_group"
    bl_label = "Remove Group"
    
    @classmethod
    def poll(cls, context):
        return context.scene.wynn_onion.groups
    
    def execute(self, context):
        settings = context.scene.wynn_onion
        settings.groups.remove(settings.active_group_index)
        settings.active_group_index = max(0, min(settings.active_group_index, len(settings.groups) - 1))
        return {'FINISHED'}

class WYNN_OT_add_selected_to_onion_group(bpy.types.Operator):
    """Add selected objects to the active group"""
    bl_idname = "wynn.add_selected_to_onion_group"
    bl_label = "Add Selected"
    
    @classmethod
    def poll(cls, context):
        return context.scene.wynn_onion.groups and context.selected_objects
    
    def execute(self, context):
        settings = context.scene.wynn_onion
        group = settings.groups[settings.active_group_index]
        
        added_count = 0
        current_objs = {item.obj for item in group.objects}
        
        for obj in context.selected_objects:
            if obj not in current_objs:
                item = group.objects.add()
                item.obj = obj
                item.name = obj.name
                added_count += 1
                
        if added_count > 0:
            self.report({'INFO'}, f"Added {added_count} objects to {group.name}")
        else:
            self.report({'WARNING'}, "Selected objects are already in the group")
            
        return {'FINISHED'}

class WYNN_OT_remove_onion_object(bpy.types.Operator):
    """Remove inactive object from the group list"""
    bl_idname = "wynn.remove_onion_object"
    bl_label = "Remove Object"
    
    def execute(self, context):
        settings = context.scene.wynn_onion
        group = settings.groups[settings.active_group_index]
        if group.objects and group.active_object_index < len(group.objects):
            group.objects.remove(group.active_object_index)
        return {'FINISHED'}

class WYNN_OT_update_onion_skin(bpy.types.Operator):
    """Update cache for onion skinning (Calculates meshes for ghosts)"""
    bl_idname = "wynn.update_onion_skin"
    bl_label = "Update Ghosts"
    
    def execute(self, context):
        global ONION_SKIN_CACHE
        ONION_SKIN_CACHE = {} # Clear old cache on update
        
        settings = context.scene.wynn_onion
        if not settings.is_enabled:
            return {'CANCELLED'}
            
        depsgraph = context.evaluated_depsgraph_get()
        scene = context.scene
        current_frame = scene.frame_current
        
        frames_to_cache = set()
        
        # Collect Objects first to check keyframes
        objects_to_cache = set()
        for group in settings.groups:
            if group.is_active:
                for item in group.objects:
                    if item.obj:
                        objects_to_cache.add(item.obj)
        
        if not objects_to_cache:
            return {'FINISHED'}

        # Calculate Frames to Cache
        if settings.use_keyframe_only:
            # Union of keyframes from all objects (simplified)
            # Ideally we cache per-object, but that requires complex scene stepping.
            # For performance, we take the union of all relevant keyframes and cache all objects there.
            
            union_before = set()
            union_after = set()
            
            for obj in objects_to_cache:
                 b, a = get_nearby_keyframes(obj, current_frame, settings.frame_before, settings.frame_after)
                 union_before.update(b)
                 union_after.update(a)
            
            # Since we can't easily prioritize which keyframe 'wins' if they differ,
            # we just take the sorted union. This might result in more ghosts than 'frame_before' count
            # if objects have staggered keys.
            # To respect the count strictly, we sort and slice AGAIN.
            
            final_before = sorted(list(union_before))[-settings.frame_before:] if settings.frame_before > 0 else []
            final_after = sorted(list(union_after))[:settings.frame_after] if settings.frame_after > 0 else []
            
            frames_to_cache.update(final_before)
            frames_to_cache.update(final_after)
            
        else:
            # Standard Step Logic
            # For Before
            for i in range(1, settings.frame_before + 1):
                if i % settings.step == 0:
                    frames_to_cache.add(current_frame - i)
            # For After
            for i in range(1, settings.frame_after + 1):
                if i % settings.step == 0:
                    frames_to_cache.add(current_frame + i)
        
        # Calculate Batches
        saved_frame = scene.frame_current
        
        try:
            for frame in frames_to_cache:
                scene.frame_set(frame)
                # Force update dependencies to ensure we get the mesh at this new frame
                context.view_layer.update() 
                
                for obj in objects_to_cache:
                    if obj.name not in ONION_SKIN_CACHE:
                        ONION_SKIN_CACHE[obj.name] = {}
                        
                    # Check if already cached (Optional: add forced refresh arg)
                    # if frame in ONION_SKIN_CACHE[obj.name]: continue
                    
                    # Evaluate Mesh
                    try:
                        eval_obj = obj.evaluated_get(context.evaluated_depsgraph_get())
                        mesh = eval_obj.to_mesh()
                        
                        # Create Batch
                        # We need to transform Local Coords to World Coords
                        matrix_world = eval_obj.matrix_world
                        coords = [matrix_world @ v.co for v in mesh.vertices]
                        
                        # Generate Triangle Indices for Solid Surface rendering
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
                        
                        # Debug
                        print(f"Cached {obj.name} at frame {frame} (Solid): {len(coords)} verts")
                        
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        print(f"Error caching {obj.name} at {frame}: {e}")
                        
        finally:
            scene.frame_set(saved_frame)
            
        return {'FINISHED'}

class WYNN_OT_select_onion_group_objects(bpy.types.Operator):
    """Select all objects in this group"""
    bl_idname = "wynn.select_onion_group_objects"
    bl_label = "Select Group Objects"
    
    def execute(self, context):
        settings = context.scene.wynn_onion
        group = settings.groups[settings.active_group_index]
        
        for item in group.objects:
            if item.obj:
                item.obj.select_set(True)
        return {'FINISHED'}

# -------------------------------------------------------------------
#   Registration
# -------------------------------------------------------------------

classes = (
    OnionSkinObjectItem,
    OnionSkinGroup,
    OnionSkinSettings,
    WYNN_OT_add_onion_group,
    WYNN_OT_remove_onion_group,
    WYNN_OT_add_selected_to_onion_group,
    WYNN_OT_remove_onion_object,
    WYNN_OT_select_onion_group_objects,
    WYNN_OT_update_onion_skin,
)

# -------------------------------------------------------------------
#   Draw Handler
# -------------------------------------------------------------------

def draw_onion_skins():
    context = bpy.context
    settings = context.scene.wynn_onion
    
    if not settings.is_enabled:
        return
        
    current_frame = context.scene.frame_current
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    shader.bind()
    
    # Enable Blending for opacity
    gpu.state.blend_set('ALPHA')
    # Enable X-Ray (Disable Depth Testing) so lines show through the character
    gpu.state.depth_test_set('NONE')
    
    try:
        # Iterate Groups
        for group in settings.groups:
            if not group.is_active: continue
            
            for item in group.objects:
                obj = item.obj
                if not obj: continue
                if obj.name not in ONION_SKIN_CACHE: continue
                
                cached_frames = ONION_SKIN_CACHE[obj.name]
                
                # Draw Before
                shader.uniform_float("color", (*settings.color_before, settings.opacity))
                for i in range(1, settings.frame_before + 1):
                    if i % settings.step == 0:
                        frame = current_frame - i
                        if frame in cached_frames:
                            batch = cached_frames[frame]
                            batch.draw(shader)
                            
                # Draw After
                shader.uniform_float("color", (*settings.color_after, settings.opacity))
                for i in range(1, settings.frame_after + 1):
                    if i % settings.step == 0:
                        frame = current_frame + i
                        if frame in cached_frames:
                            batch = cached_frames[frame]
                            batch.draw(shader)

    except Exception as e:
        pass # Draw handlers should be robust
        
    finally:
        # Restore State
        gpu.state.blend_set('NONE')
        # Restore Depth Testing (Standard 3D behavior)
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
    
    if settings.is_enabled:
        row.operator("wynn.update_onion_skin", text="", icon='FILE_REFRESH')
    
    if not settings.is_enabled:
        # layout.active = False # Optional: Disable UI if off
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
    
    box.prop(settings, "step")
    box.prop(settings, "use_keyframe_only")
    box.prop(settings, "opacity", slider=True)
    
    # Groups
    box = layout.box()
    row = box.row()
    row.label(text="Groups")
    
    if settings.groups:
        row = box.row()
        row.template_list("UI_UL_list", "onion_groups", settings, "groups", settings, "active_group_index", rows=3)
        
        col = row.column(align=True)
        col.operator("wynn.add_onion_group", text="", icon='ADD')
        col.operator("wynn.remove_onion_group", text="", icon='REMOVE')
        
        # Active Group Controls
        if settings.active_group_index < len(settings.groups):
            group = settings.groups[settings.active_group_index]
            
            g_box = box.box()
            # Header with checkbox
            row = g_box.row()
            row.prop(group, "is_active", text="")
            row.prop(group, "name", text="")
            
            # Actions
            row = g_box.row(align=True)
            row.operator("wynn.add_selected_to_onion_group", text="Add Selected", icon='ADD')
            row.operator("wynn.select_onion_group_objects", text="Select All", icon='RESTRICT_SELECT_OFF')
            
            # Objects List
            g_box.label(text="Objects in Group:")
            row = g_box.row()
            row.template_list("UI_UL_list", "onion_objects", group, "objects", group, "active_object_index", rows=4)
            
            col = row.column(align=True)
            col.operator("wynn.remove_onion_object", text="", icon='REMOVE')
            
    else:
        box.operator("wynn.add_onion_group", text="Add New Group", icon='ADD')

# -------------------------------------------------------------------
#   Draw Logic
#   DRAW HANDLER
# -------------------------------------------------------------------

def draw_onion_skins():
    context = bpy.context
    settings = context.scene.wynn_onion
    
    if not settings.is_enabled:
        return
        
    current_frame = context.scene.frame_current
    try:
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    except:
        shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
        
    shader.bind()
    
    # Enable Blending for opacity
    gpu.state.blend_set('ALPHA')
    # Enable X-Ray
    gpu.state.depth_test_set('NONE')
    
    try:
        # Iterate Groups
        for group in settings.groups:
            if not group.is_active: continue
            
            for item in group.objects:
                obj = item.obj
                if not obj: continue
                if obj.name not in ONION_SKIN_CACHE: continue
                
                cached_frames = ONION_SKIN_CACHE[obj.name]
                
                # We simply iterate over what we have cached.
                # The logic for WHAT to cache is now handled by the Update Operator.
                # However, we still want to respect color_before / color_after distinction based on frame number.
                
                for frame, batch in cached_frames.items():
                    if frame < current_frame:
                         shader.uniform_float("color", (*settings.color_before, settings.opacity))
                         batch.draw(shader)
                    elif frame > current_frame:
                         shader.uniform_float("color", (*settings.color_after, settings.opacity))
                         batch.draw(shader)

    except Exception as e:
        pass 
        
    finally:
        # Restore State
        gpu.state.blend_set('NONE')
        gpu.state.depth_test_set('LESS_EQUAL')
