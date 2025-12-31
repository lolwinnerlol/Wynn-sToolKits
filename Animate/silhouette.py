import bpy

# Define the Operator for the Silhouette Tool
class WM_OT_silhouette_tool(bpy.types.Operator):
    """Toggles a silhouette shading style for the 3D Viewport"""
    bl_idname = "wm.silhouette_tool"
    bl_label = "Silhouette Tool"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Access our custom properties stored on the window manager
        stored_props = context.window_manager.wynn_animator_props
        addon_name = __package__.split(".")[0]
        prefs = context.preferences.addons[addon_name].preferences
        
        # Ensure the operator is being called from a 3D Viewport
        if context.space_data.type != 'VIEW_3D':
            self.report({'WARNING'}, "This tool can only be used in the 3D Viewport.")
            return {'CANCELLED'}

        shading = context.space_data.shading
        overlay = context.space_data.overlay
        scene = context.scene

        def traverse_layer_objects(layer_coll, callback):
            callback(layer_coll)
            for child in layer_coll.children:
                traverse_layer_objects(child, callback)

        try:
            # Check if silhouette mode is already active
            if stored_props.is_silhouette_active:
                # --- TOGGLE OFF: Restore original settings ---
                shading.light = stored_props.light
                shading.color_type = stored_props.color_type
                shading.single_color = stored_props.single_color
                shading.background_type = stored_props.background_type
                shading.background_color = stored_props.background_color
                shading.wireframe_color_type = stored_props.wireframe_color_type
                
                if prefs.toggle_overlays:
                    overlay.show_overlays = stored_props.show_overlays
                
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

                stored_props.is_silhouette_active = False
                self.report({'INFO'}, "Silhouette mode disabled. Viewport restored.")
            else:
                # --- TOGGLE ON: Store current settings and apply new ones ---
                
                # Store the user's current settings
                stored_props.light = shading.light
                stored_props.color_type = shading.color_type
                stored_props.single_color = shading.single_color
                stored_props.background_type = shading.background_type
                stored_props.background_color = shading.background_color
                stored_props.wireframe_color_type = shading.wireframe_color_type
                
                if prefs.toggle_overlays:
                    stored_props.show_overlays = overlay.show_overlays

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

                # Apply the silhouette settings
                shading.light = 'FLAT'
                shading.color_type = 'SINGLE'
                shading.single_color = prefs.silhouette_color
                shading.background_type = 'VIEWPORT'
                shading.background_color = prefs.background_color

                if prefs.toggle_overlays:
                    overlay.show_overlays = False
                
                stored_props.is_silhouette_active = True
                self.report({'INFO'}, "Silhouette mode enabled.")

            return {'FINISHED'}
        except Exception as e:
            # Reset the flag on error to prevent getting stuck in a bad state
            stored_props.is_silhouette_active = False
            self.report({'ERROR'}, f"Failed to toggle silhouette mode: {e}")
            return {'CANCELLED'}
