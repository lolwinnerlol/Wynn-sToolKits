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
