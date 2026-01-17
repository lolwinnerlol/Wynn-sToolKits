import bpy

# Define the Operator for the Silhouette Tool
# Store state per viewport to handle multiple windows correctly
# Key: context.space_data (SpaceView3D)
# Value: dict containing:
#   'shading': dict of shading properties
#   'overlay': bool (show_overlays)
#   'is_active': bool
viewport_state_store = {}

def get_silhouette_target_objects(scene):
    """Helper to determine which objects should be in silhouette based on settings"""
    target_objects = set()
    
    # Logic: Check Onion Skin Group first, then standard CharacterMesh
    use_onion_group = False
    if hasattr(scene, "wynn_onion") and scene.wynn_onion.use_silhouette_group:
        if scene.wynn_onion.groups and scene.wynn_onion.active_group_index < len(scene.wynn_onion.groups):
            group = scene.wynn_onion.groups[scene.wynn_onion.active_group_index]
            onion_group_objects = {item.obj for item in group.objects if item.obj}
            if onion_group_objects:
                target_objects = onion_group_objects
                use_onion_group = True
    
    if not use_onion_group:
        # Fallback to standard CharacterMesh / Selection logic
        for obj in scene.objects:
            is_in_char_mesh = False
            for col in obj.users_collection:
                if col.name.startswith("CharacterMesh"):
                    is_in_char_mesh = True
                    break
            
            if is_in_char_mesh or obj.select_get():
                target_objects.add(obj)
                
    return target_objects

def enter_local_view_safe(context, target_objects):
    """
    Safely enters Local View with specific objects, handling Mode switching.
    Requires context to be overridden to the target 3D View.
    """
    if not target_objects: return

    # 1. Save Mode and Selection
    original_mode = context.mode
    saved_selection = [obj for obj in context.selected_objects]
    active_obj = context.active_object
    
    try:
        # 2. Switch to Object Mode (Required for selection ops)
        if original_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
            
        # 3. Select ONLY target objects
        bpy.ops.object.select_all(action='DESELECT')
        for obj in target_objects:
            obj.select_set(True)
        
        # 4. Enter Local View (if not already)
        if not context.space_data.local_view:
            bpy.ops.view3d.localview(frame_selected=False)
            
        # 5. Restore Selection
        # Note: In Local View, objects not in it are invisible/unselectable.
        # We try to restore what we can.
        bpy.ops.object.select_all(action='DESELECT')
        for obj in saved_selection:
            # Check if object is actually in the view layer (it should be)
            if obj.name in context.view_layer.objects:
                # In Local View, check if it's actually visible/selectable?
                # select_set won't crash if hidden, just might not work.
                obj.select_set(True)
                
        if active_obj and active_obj.name in context.view_layer.objects:
             context.view_layer.objects.active = active_obj

    except Exception as e:
        print(f"Error entering local view: {e}")
        
    finally:
        # 6. Restore Mode
        if original_mode != 'OBJECT':
             # Ensure active object allows switching back (e.g. valid armature for Pose)
             # If active object changed or is invalid, this might fail, but we try.
             try:
                 if active_obj and context.view_layer.objects.active != active_obj:
                      context.view_layer.objects.active = active_obj
                 
                 bpy.ops.object.mode_set(mode=original_mode)
             except:
                 pass # Fallback to Object Mode if restore fails

def update_silhouette_visibility(context):
    """
    Updates the Local View of active Silhouette viewports.
    Call this when settings change (e.g. active group switches).
    """
    global viewport_state_store
    scene = context.scene
    
    # 1. Identify Target Objects (New Group)
    target_objects = get_silhouette_target_objects(scene)
    
    # 2. Iterate ALL Viewports to find active ones
    for window in context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        # Check if this space is in our store and Active
                        if space in viewport_state_store and viewport_state_store[space].get('is_active'):
                             # Found an active silhouette viewport!
                             
                             # Find Region (needed for override)
                             region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                             if not region: continue
                             
                             # Override Context to target this Viewport
                             with context.temp_override(window=window, screen=screen, area=area, region=region):
                                 
                                 # A. Exit Local View if in it (to reset)
                                 if space.local_view: 
                                      bpy.ops.view3d.localview() 
                                 
                                 # B. Re-Enter Safe
                                 enter_local_view_safe(context, target_objects)


class WM_OT_silhouette_tool(bpy.types.Operator):
    """Toggles a silhouette shading style for the 3D Viewport using Local View"""
    bl_idname = "wm.silhouette_tool"
    bl_label = "Silhouette Tool"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        global viewport_state_store

        # Access user preferences
        addon_name = __package__.split(".")[0]
        prefs = context.preferences.addons[addon_name].preferences
        
        # Ensure the operator is being called from a 3D Viewport
        if context.space_data.type != 'VIEW_3D':
            self.report({'WARNING'}, "This tool can only be used in the 3D Viewport.")
            return {'CANCELLED'}

        shading = context.space_data.shading
        overlay = context.space_data.overlay
        scene = context.scene
        current_space = context.space_data
        
        # Check if THIS viewport is already active
        is_active_here = False
        if current_space in viewport_state_store:
            is_active_here = viewport_state_store[current_space].get('is_active', False)

        try:
            if is_active_here:
                # --- TOGGLE OFF: Restore original listener settings ---
                
                saved_state = viewport_state_store[current_space]
                
                # Exit Local View if we are in it
                if context.space_data.local_view:
                     bpy.ops.view3d.localview()

                # Restore Shading
                if 'shading' in saved_state:
                    s_props = saved_state['shading']
                    shading.light = s_props.get('light', 'STUDIO')
                    shading.color_type = s_props.get('color_type', 'MATERIAL')
                    shading.single_color = s_props.get('single_color', (0,0,0))
                    shading.background_type = s_props.get('background_type', 'THEME')
                    shading.background_color = s_props.get('background_color', (0,0,0))
                    shading.wireframe_color_type = s_props.get('wireframe_color_type', 'THEME')

                # Restore Overlay
                if prefs.toggle_overlays and 'overlay' in saved_state:
                    overlay.show_overlays = saved_state['overlay']
                
                # Remove this viewport from store
                del viewport_state_store[current_space]
                
                # Update global legacy flag for UI consistency (if no other viewports active)
                any_other_active = any(v.get('is_active', False) for k, v in viewport_state_store.items() if k != current_space)
                if not any_other_active:
                    stored_props = getattr(context.window_manager, "wynn_animator_props", None)
                    if stored_props:
                        stored_props.is_silhouette_active = False

                self.report({'INFO'}, "Silhouette mode disabled for this Viewport.")
                
            else:
                # --- TOGGLE ON: Store settings and apply new ones ---
                
                # 1. Capture State
                state = {
                    'is_active': True,
                    'shading': {
                        'light': shading.light,
                        'color_type': shading.color_type,
                        'single_color': list(shading.single_color),
                        'background_type': shading.background_type,
                        'background_color': list(shading.background_color),
                        'wireframe_color_type': shading.wireframe_color_type
                    }
                }
                
                if prefs.toggle_overlays:
                    state['overlay'] = overlay.show_overlays
                
                viewport_state_store[current_space] = state

                # 2. Identify Objects for Silhouette
                target_objects = get_silhouette_target_objects(scene)

                # 3. Enter Local View with specific objects (SAFE MODE)
                if target_objects:
                    enter_local_view_safe(context, target_objects)

                # 4. Apply Shading Settings
                shading.light = 'FLAT'
                shading.color_type = 'SINGLE'
                shading.single_color = prefs.silhouette_color
                shading.background_type = 'VIEWPORT'
                shading.background_color = prefs.background_color

                if prefs.toggle_overlays:
                    overlay.show_overlays = False
                
                # Update global legacy flag
                stored_props = getattr(context.window_manager, "wynn_animator_props", None)
                if stored_props:
                    stored_props.is_silhouette_active = True
                
                self.report({'INFO'}, "Silhouette mode enabled.")

            return {'FINISHED'}
        except Exception as e:
            # Clean up on error
            if current_space in viewport_state_store:
                del viewport_state_store[current_space]
            
            # Reset global flag if needed
            any_other_active = any(v.get('is_active', False) for k, v in viewport_state_store.items() if k != current_space)
            if not any_other_active:
                stored_props = getattr(context.window_manager, "wynn_animator_props", None)
                if stored_props: stored_props.is_silhouette_active = False

            self.report({'ERROR'}, f"Failed to toggle silhouette mode: {e}")
            return {'CANCELLED'}
