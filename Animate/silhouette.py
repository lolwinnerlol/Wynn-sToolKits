import bpy

# Define the Operator for the Silhouette Tool
# Store state per viewport to handle multiple windows correctly
# Key: context.space_data (SpaceView3D)
# Value: dict containing:
#   'shading': dict of shading properties
#   'overlay': bool (show_overlays)
#   'is_active': bool
viewport_state_store = {}

class WM_OT_silhouette_tool(bpy.types.Operator):
    """Toggles a silhouette shading style for the 3D Viewport"""
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

        # Helper for traversing layer collection
        def traverse_layer_objects(layer_coll, callback):
            callback(layer_coll)
            for child in layer_coll.children:
                traverse_layer_objects(child, callback)

        # Check if THIS viewport is already active
        is_active_here = False
        if current_space in viewport_state_store:
            is_active_here = viewport_state_store[current_space].get('is_active', False)

        try:
            if is_active_here:
                # --- TOGGLE OFF: Restore original listener settings ---
                
                saved_state = viewport_state_store[current_space]
                
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
                
                # --- GLOBAL VISIBILITY MANAGEMENT ---
                # Only restore global object visibility if NO OTHER viewport is active
                any_other_active = any(v.get('is_active', False) for k, v in viewport_state_store.items() if k != current_space)
                
                if not any_other_active:
                    # Restore collection visibility
                    if "wynn_silhouette_restore" in scene:
                        def restore_callback(lc):
                            if lc.name in scene["wynn_silhouette_restore"]:
                                lc.hide_viewport = scene["wynn_silhouette_restore"][lc.name]
                        
                        traverse_layer_objects(context.view_layer.layer_collection, restore_callback)
                        del scene["wynn_silhouette_restore"]

                    # Restore object visibility
                    if "wynn_silhouette_restore_objects" in scene:
                        restore_objs = scene["wynn_silhouette_restore_objects"]
                        for obj_name, state in restore_objs.items():
                            if obj_name in scene.objects:
                                scene.objects[obj_name].hide_viewport = state
                        del scene["wynn_silhouette_restore_objects"]
                    
                    # Update global legacy flag for UI consistency (if referenced elsewhere)
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

                # 2. Check Global Visibility State
                # If "wynn_silhouette_restore" exists, assumes objects are ALREADY hidden/configured by another window.
                # In that case, we SKIP the visibility processing to avoid overwriting the clean restore state with the already-hidden state.
                already_globally_active = ("wynn_silhouette_restore" in scene or "wynn_silhouette_restore_objects" in scene)

                if not already_globally_active:
                    # Capture and Apply Object Visibility (Global)
                    
                    # Store collection visibility and Hide others
                    restore_data = {}
                    
                    def process_visibility(lc):
                        # Skip root for storage/hiding, but traverse children
                        is_root = (lc == context.view_layer.layer_collection)
                        
                        if not is_root:
                            restore_data[lc.name] = lc.hide_viewport
                        
                        is_target_collection = lc.collection.name.startswith("CharacterMesh")
                        
                        has_selected_obj = False
                        for obj in lc.collection.objects:
                            if obj.select_get():
                                has_selected_obj = True
                                break

                        has_visible_descendant = False
                        
                        for child in lc.children:
                            if process_visibility(child):
                                has_visible_descendant = True
                                
                        should_be_visible = is_target_collection or has_visible_descendant or has_selected_obj
                        
                        if not is_root:
                            lc.hide_viewport = not should_be_visible
                            
                        return should_be_visible
                    
                    process_visibility(context.view_layer.layer_collection)
                    scene["wynn_silhouette_restore"] = restore_data

                    # Store object visibility and Hide others
                    restore_objs = {}
                    for obj in scene.objects:
                        is_in_char_mesh = False
                        for col in obj.users_collection:
                            if col.name.startswith("CharacterMesh"):
                                is_in_char_mesh = True
                                break
                        
                        if not is_in_char_mesh and not obj.select_get():
                            restore_objs[obj.name] = obj.hide_viewport
                            obj.hide_viewport = True
                    scene["wynn_silhouette_restore_objects"] = restore_objs
                    
                    # Update global legacy flag
                    stored_props = getattr(context.window_manager, "wynn_animator_props", None)
                    if stored_props:
                        stored_props.is_silhouette_active = True

                # 3. Apply Local Settings
                shading.light = 'FLAT'
                shading.color_type = 'SINGLE'
                shading.single_color = prefs.silhouette_color
                shading.background_type = 'VIEWPORT'
                shading.background_color = prefs.background_color

                if prefs.toggle_overlays:
                    overlay.show_overlays = False
                
                self.report({'INFO'}, "Silhouette mode enabled.")

            return {'FINISHED'}
        except Exception as e:
            # Clean up on error
            if current_space in viewport_state_store:
                del viewport_state_store[current_space]
            
            # If no one else is active, try to clear scene flags to unstick
            any_other_active = any(v.get('is_active', False) for k, v in viewport_state_store.items() if k != current_space)
            if not any_other_active:
                stored_props = getattr(context.window_manager, "wynn_animator_props", None)
                if stored_props: stored_props.is_silhouette_active = False

            self.report({'ERROR'}, f"Failed to toggle silhouette mode: {e}")
            return {'CANCELLED'}
