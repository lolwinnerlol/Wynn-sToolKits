import bpy
import json
import os
import re

class WYNN_OT_import_rig(bpy.types.Operator):
    """Import and replace rig based on JSON configuration"""
    bl_idname = "wynn.import_rig"
    bl_label = "Import Rig"
    bl_description = "Replace current character rig with the latest version from configuration"
    bl_options = {'REGISTER', 'UNDO'}

    # Path to the JSON configuration file
    CONFIG_PATH = r"X:\My Drive\80_Resources\DataReader\CollectionImport.json"

    def invoke(self, context, event):
        # Pre-check for collection existence to prompt user
        if os.path.exists(self.CONFIG_PATH):
            try:
                with open(self.CONFIG_PATH, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                current_char_id = config.get("current_character_id")
                
                if current_char_id:
                    # Check if collection exists in scene
                    found = False
                    for col in bpy.data.collections:
                         if col.name == current_char_id or re.match(f"^{re.escape(current_char_id)}\\.\\d{{3}}$", col.name):
                            if col in context.scene.collection.children_recursive:
                                found = True
                                break
                    
                    if not found:
                        self.missing_collection = current_char_id
                        return context.window_manager.invoke_props_dialog(self, width=400)
            except Exception as e:
                print(f"[Wynn] Invoke Check Failed: {e}")
        
        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text=f"No '{getattr(self, 'missing_collection', 'Collection')}' detected.")
        col.label(text="Import as new collection?")

    def execute(self, context):
        print(f"\n[Wynn] Starting Import Rig Process...")

        # Ensure Object Mode
        if context.active_object and context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # 1. Read JSON Configuration
        if not os.path.exists(self.CONFIG_PATH):
            self.report({'ERROR'}, f"Config file not found: {self.CONFIG_PATH}")
            return {'CANCELLED'}

        try:
            with open(self.CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to parse JSON: {e}")
            return {'CANCELLED'}

        current_char_id = config.get("current_character_id")
        import_char_id = config.get("import_character_id")
        latest_rig_path = config.get("latest_rig_file_path")
        characters_map = config.get("characters", {})

        print(f"[Wynn] Config Loaded: Current={current_char_id}, Import={import_char_id}")

        if not all([current_char_id, import_char_id, latest_rig_path]):
            self.report({'ERROR'}, "Missing required fields in JSON config")
            return {'CANCELLED'}

        # Get import collection name from the map
        if import_char_id not in characters_map:
             self.report({'ERROR'}, f"Character ID '{import_char_id}' not found in 'characters' map")
             return {'CANCELLED'}
        
        target_collection_name = characters_map[import_char_id].get("collection_name")
        if not target_collection_name:
             self.report({'ERROR'}, f"No 'collection_name' defined for '{import_char_id}'")
             return {'CANCELLED'}

        # 2. Identify and Process Old Collection
        old_collection = None
        
        candidate_collections = []
        for col in bpy.data.collections:
            # Check if name is exactly ID or ID.number (ignoring .### suffix)
            if col.name == current_char_id or re.match(f"^{re.escape(current_char_id)}\\.\\d{{3}}$", col.name):
                candidate_collections.append(col)
        
        # Filter by present in current scene to be safe
        scene_collections = set(context.scene.collection.children_recursive)
        candidate_collections = [c for c in candidate_collections if c in scene_collections]
        
        if not candidate_collections:
             # self.report({'ERROR'}, f"No matching collection found in the current scene for '{current_char_id}'")
             # return {'CANCELLED'}
             print(f"[Wynn] No old collection found for '{current_char_id}'. Importing as new.")
             old_collection = None
        else:
            old_collection = candidate_collections[0]
            print(f"[Wynn] Found Old Collection: {old_collection.name}")
        
        # 3. Preserve Data (Transforms, Action, and NLA)
        saved_transforms = None
        saved_action = None
        saved_action_slot = None
        saved_parent_col = None
        saved_nla_data = [] # List of tracks

        if old_collection:
            # Find parent collection
            # Check scene root first
            if old_collection.name in context.scene.collection.children:
                saved_parent_col = context.scene.collection
            else:
                # Check all collections (bfs/scan)
                for col in bpy.data.collections:
                    if old_collection.name in col.children:
                        saved_parent_col = col
                        break
            
            if not saved_parent_col:
                saved_parent_col = context.scene.collection # Fallback
                print("[Wynn] Warning: specific parent not found, defaulting to Scene Collection")

            # Find Armature in old collection
            old_armature_obj = None
            for obj in old_collection.all_objects:
                if obj.type == 'ARMATURE':
                    old_armature_obj = obj
                    break
            
            if old_armature_obj:
                saved_transforms = old_armature_obj.matrix_world.copy()
                print(f"[Wynn] Saved Transforms from {old_armature_obj.name}")
                
                if old_armature_obj.animation_data:
                    if old_armature_obj.animation_data.action:
                        saved_action = old_armature_obj.animation_data.action
                        print(f"[Wynn] Saved Active Action: {saved_action.name}")
                    
                    # Save Animation Slot (Blender 5.0+)
                    if hasattr(old_armature_obj.animation_data, "action_slot"):
                        saved_action_slot = old_armature_obj.animation_data.action_slot
                        slot_name = getattr(saved_action_slot, 'name_display', 'Unknown')
                        print(f"[Wynn] Saved Action Slot: {slot_name}")
                    else:
                        saved_action_slot = None

                    # Verify and Save NLA Tracks
                    if old_armature_obj.animation_data.nla_tracks:
                        print(f"[Wynn] Found {len(old_armature_obj.animation_data.nla_tracks)} NLA Tracks. Saving...")
                        for track in old_armature_obj.animation_data.nla_tracks:
                            track_data = {
                                "name": track.name,
                                "is_solo": track.is_solo,
                                "mute": track.mute,
                                "strips": []
                            }
                            for strip in track.strips:
                                strip_data = {
                                    "name": strip.name,
                                    "frame_start": strip.frame_start,
                                    "frame_end": strip.frame_end,
                                    "action": strip.action, # Reference to Action datablock (persists)
                                    "blend_type": strip.blend_type,
                                    "extrapolation": strip.extrapolation,
                                    "use_auto_blend": strip.use_auto_blend,
                                    "use_reverse": strip.use_reverse,
                                    "use_sync_length": strip.use_sync_length,
                                    # Add more props if needed (scale, repeat, etc)
                                }
                                track_data["strips"].append(strip_data)
                            saved_nla_data.append(track_data)
                else:
                     print("[Wynn] No animation data on old rig.")
            else:
                self.report({'WARNING'}, "No armature found in old collection. Animation/Transforms won't be synced.")
                print("[Wynn] No armature found in old collection.")

            # Store old armature name for matching
            old_armature_name_base = old_armature_obj.name.split('.')[0] if old_armature_obj else None

            # 4. Remove Old Collection
            print("[Wynn] Removing Old Collection...")
            saved_parent_col.children.unlink(old_collection)
            
            # Collect objects to remove (safely)
            objects_to_remove = [o for o in old_collection.objects]
            for obj in objects_to_remove:
                try:
                    bpy.data.objects.remove(obj, do_unlink=True)
                except:
                    pass # Already removed?
                
            bpy.data.collections.remove(old_collection)
        else:
             print("[Wynn] Skipping data preservation and removal (Old collection not found).")
             saved_parent_col = context.scene.collection
             old_armature_name_base = None


        # 5. Append New Collection
        print(f"[Wynn] Appending from: {latest_rig_path}")
        if not os.path.exists(latest_rig_path):
             self.report({'ERROR'}, f"Rig file path not found: {latest_rig_path}")
             return {'CANCELLED'}

        with bpy.data.libraries.load(latest_rig_path, link=False) as (data_from, data_to):
            if target_collection_name in data_from.collections:
                data_to.collections = [target_collection_name]
            else:
                 self.report({'ERROR'}, f"Collection '{target_collection_name}' not found in '{latest_rig_path}'")
                 return {'CANCELLED'}

        new_collection = None
        if data_to.collections:
            new_collection = data_to.collections[0]

        if not new_collection:
             self.report({'ERROR'}, "Failed to append collection")
             return {'CANCELLED'}

        # 6. Link and Restore
        print(f"[Wynn] Linking New Collection '{new_collection.name}' to '{saved_parent_col.name}'")
        saved_parent_col.children.link(new_collection)

        # Force scene update to ensure objects are available?
        context.view_layer.update()

        # Find new Armature (Recursive search)
        # Logic: Find ALL armatures, try to match name with old one, otherwise pick first.
        new_armatures = []
        for obj in new_collection.all_objects:
            if obj.type == 'ARMATURE':
                new_armatures.append(obj)
        
        print(f"[Wynn] Found {len(new_armatures)} armatures in new collection: {[a.name for a in new_armatures]}")
        
        new_armature_obj = None
        if new_armatures:
            if len(new_armatures) == 1:
                new_armature_obj = new_armatures[0]
            else:
                # Try to fuzzy match name
                if old_armature_name_base:
                    for arm in new_armatures:
                        if arm.name.startswith(old_armature_name_base):
                            new_armature_obj = arm
                            break
                
                # Fallback to first if no match
                if not new_armature_obj:
                    new_armature_obj = new_armatures[0]
                    print("[Wynn] Could not match name, using first found armature.")

        if new_armature_obj:
            print(f"[Wynn] Selected Target Armature: {new_armature_obj.name}")
            
            # Make Active and Selected
            bpy.ops.object.select_all(action='DESELECT')
            new_armature_obj.select_set(True)
            context.view_layer.objects.active = new_armature_obj
            
            # Apply Transforms
            if saved_transforms:
                new_armature_obj.matrix_world = saved_transforms
                print("[Wynn] Applied Transforms (matrix_world)")
            
            # Ensure Animation Data exists
            if not new_armature_obj.animation_data:
                new_armature_obj.animation_data_create()
            
            # Apply Action and Slot
            if saved_action:
                new_armature_obj.animation_data.action = saved_action
                print(f"[Wynn] Applied Active Action: {saved_action.name}")
            
            if saved_action_slot:
                if hasattr(new_armature_obj.animation_data, "action_slot"):
                     try:
                        # Depending on API, we might need to find the slot or assign the object
                        # If it's a pointer to an ActionSlot, we need to find the equivalent slot in the new action?
                        # Or checking if it's just a handle.
                        # Assuming direct assignment works if it's the same Action datablock.
                        new_armature_obj.animation_data.action_slot = saved_action_slot
                        slot_name = getattr(saved_action_slot, 'name_display', 'Unknown')
                        print(f"[Wynn] Applied Action Slot: {slot_name}")
                     except Exception as e:
                        print(f"[Wynn] Failed to apply Action Slot: {e}")
                
            # Restore NLA Tracks
            if saved_nla_data:
                print(f"[Wynn] Restoring {len(saved_nla_data)} NLA Tracks...")
                for track_data in saved_nla_data:
                    new_track = new_armature_obj.animation_data.nla_tracks.new()
                    new_track.name = track_data["name"]
                    new_track.is_solo = track_data["is_solo"]
                    new_track.mute = track_data["mute"]
                    
                    for strip_data in track_data["strips"]:
                        try:
                            # Add strip
                            new_strip = new_track.strips.new(
                                name=strip_data["name"],
                                start=int(strip_data["frame_start"]),
                                action=strip_data["action"]
                            )
                            # Set properties
                            new_strip.frame_end = int(strip_data["frame_end"])
                            new_strip.blend_type = strip_data["blend_type"]
                            new_strip.extrapolation = strip_data["extrapolation"]
                            new_strip.use_auto_blend = strip_data["use_auto_blend"]
                            new_strip.use_reverse = strip_data["use_reverse"]
                            new_strip.use_sync_length = strip_data["use_sync_length"]
                        except Exception as e:
                            print(f"[Wynn] Error restoring NLA strip '{strip_data['name']}': {e}")
                print("[Wynn] NLA Restore Complete")
            
        else:
             print("[Wynn] Error: No Armature found in new collection!")
             self.report({'WARNING'}, "No Armature found in imported collection!")
        
        self.report({'INFO'}, "Rig Import Completed Successfully")
        return {'FINISHED'}

classes = [
    WYNN_OT_import_rig,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
