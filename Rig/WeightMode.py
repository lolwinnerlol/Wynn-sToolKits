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

        wynn_props = context.window_manager.wynn_rig_props

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
        visibility_store = {}
        for coll in armature.data.collections:
            visibility_store[coll.name] = coll.is_visible
        
        # Using json to be safe, though a simple str cast of a dict would also work
        import json
        wynn_props.collection_visibility = json.dumps(visibility_store)

        # Set new visibility
        for coll in armature.data.collections:
            coll.is_visible = (coll == deform_collection)

        wynn_props.weight_mode_on = True
        self.report({'INFO'}, f"Weight Mode ON: Soloing '{deform_collection.name}'")

    def turn_off(self, context, armature, wynn_props):
        if not wynn_props.collection_visibility:
            # If for some reason the stored visibility is gone, just make all visible
            if hasattr(armature.data, "collections"):
                for coll in armature.data.collections:
                    if 'deform' in coll.name.lower():
                        coll.is_visible = False
                    else:
                        coll.is_visible = True
            wynn_props.weight_mode_on = False
            self.report({'INFO'}, "Weight Mode OFF: Restored visibility (no stored state found).")
            return

        import json
        visibility_store = json.loads(wynn_props.collection_visibility)

        if hasattr(armature.data, "collections"):
            for coll in armature.data.collections:
                # Restore visibility, default to True if collection is new
                coll.is_visible = visibility_store.get(coll.name, True)
                
                if 'deform' in coll.name.lower():
                    coll.is_visible = False

        wynn_props.weight_mode_on = False
        wynn_props.collection_visibility = "" # Clear stored data
        self.report({'INFO'}, "Weight Mode OFF: Restored bone collection visibility.")

def register():
    bpy.utils.register_class(WYNN_OT_toggle_weight_mode)

def unregister():
    bpy.utils.unregister_class(WYNN_OT_toggle_weight_mode)
