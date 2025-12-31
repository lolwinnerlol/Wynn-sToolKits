import bpy

class WYNN_OT_toggle_weight_mode(bpy.types.Operator):
    """Toggles weight mode, soloing the 'Deform' bone collection."""
    bl_idname = "wynn.toggle_weight_mode"
    bl_label = "Toggle Weight Mode"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj is None:
            return False
        
        if obj.type == 'ARMATURE' and obj.mode == 'POSE':
            return True
            
        if obj.type == 'MESH':
            for modifier in obj.modifiers:
                if modifier.type == 'ARMATURE' and modifier.object:
                    return True
        
        return False

    def get_armature(self, context):
        obj = context.object
        if obj.type == 'ARMATURE':
            return obj
        
        if obj.type == 'MESH':
            for modifier in obj.modifiers:
                if modifier.type == 'ARMATURE' and modifier.object:
                    return modifier.object
        
        return None

    def execute(self, context):
        armature = self.get_armature(context)
        if not armature:
            self.report({'ERROR'}, "No valid Armature found.")
            return {'CANCELLED'}

        wynn_props = getattr(context.window_manager, "wynn_rig_props", None)
        if not wynn_props:
            self.report({'ERROR'}, "Rig properties not found. Please reload the addon.")
            return {'CANCELLED'}

        if wynn_props.weight_mode_on:
            self.turn_off(context, armature, wynn_props)
        else:
            self.turn_on(context, armature, wynn_props)

        return {'FINISHED'}

    def turn_on(self, context, armature, wynn_props):
        if not hasattr(armature.data, "collections"):
            self.report({'WARNING'}, "No Bone Collections found in this Armature.")
            return

        deform_collection = None
        for collection in armature.data.collections:
            if 'deform' in collection.name.lower():
                deform_collection = collection
                break

        if not deform_collection:
            self.report({'WARNING'}, "No 'Deform' bone collection found.")
            return

        # Store current visibility
        visibility_data = {
            "collections": {},
            "wireframes": {}
        }

        # Store overlay opacity if in View3D
        if context.space_data and context.space_data.type == 'VIEW_3D':
            visibility_data["overlay_opacity"] = context.space_data.overlay.wireframe_opacity
            context.space_data.overlay.wireframe_opacity = 0.06

        for coll in armature.data.collections:
            visibility_data["collections"][coll.name] = coll.is_visible

        # Set new visibility
        deform_collection.is_solo = True

        # Turn on wireframe and store state
        def enable_wireframe_recursive(obj):
            if obj.type == 'MESH':
                visibility_data["wireframes"][obj.name] = obj.show_wire
                obj.show_wire = True
            for child in obj.children:
                enable_wireframe_recursive(child)
        
        enable_wireframe_recursive(armature)

        # Using json to be safe
        import json
        wynn_props.collection_visibility = json.dumps(visibility_data)

        wynn_props.weight_mode_on = True
        self.report({'INFO'}, f"Weight Mode ON: Soloing '{deform_collection.name}'")

    def turn_off(self, context, armature, wynn_props):
        if not wynn_props.collection_visibility:
            # If for some reason the stored visibility is gone, just make all visible
            if hasattr(armature.data, "collections"):
                for coll in armature.data.collections:
                    if 'deform' in coll.name.lower():
                        coll.is_visible = False
                        coll.is_solo = False
                    else:
                        coll.is_visible = True
            wynn_props.weight_mode_on = False
            self.report({'INFO'}, "Weight Mode OFF: Restored visibility (no stored state found).")
            return

        import json
        try:
            stored_data = json.loads(wynn_props.collection_visibility)
        except:
            stored_data = {}

        # Support both new structure and potential legacy flat dict
        if "collections" in stored_data:
            collection_states = stored_data["collections"]
            wireframe_states = stored_data.get("wireframes", {})
            overlay_opacity = stored_data.get("overlay_opacity")
        else:
            collection_states = stored_data
            wireframe_states = {}
            overlay_opacity = None

        if hasattr(armature.data, "collections"):
            for coll in armature.data.collections:
                # Restore visibility, default to True if collection is new
                coll.is_visible = collection_states.get(coll.name, True)
                
                if 'deform' in coll.name.lower():
                    coll.is_visible = False
                    coll.is_solo = False
        
        # Restore wireframes
        for obj_name, was_wire in wireframe_states.items():
            obj = bpy.data.objects.get(obj_name)
            if obj and obj.type == 'MESH':
                obj.show_wire = was_wire
        
        # Restore overlay opacity
        if overlay_opacity is not None and context.space_data and context.space_data.type == 'VIEW_3D':
            context.space_data.overlay.wireframe_opacity = overlay_opacity

        wynn_props.weight_mode_on = False
        wynn_props.collection_visibility = "" # Clear stored data
        self.report({'INFO'}, "Weight Mode OFF: Restored bone collection and wireframe visibility.")

def register():
    bpy.utils.register_class(WYNN_OT_toggle_weight_mode)

def unregister():
    bpy.utils.unregister_class(WYNN_OT_toggle_weight_mode)
