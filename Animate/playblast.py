
import bpy
import os
import re
import json

def get_animator_name():
    try:
        # Config is in the parent directory (addon root)
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("user_name", "Animator")
    except Exception as e:
        print(f"Error loading config: {e}")
    return "Animator"

def get_playblast_filename(scene):
    """Constructs the predicted filename for preview"""
    # Base name logic matches execute()
    if bpy.data.filepath:
        filename = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
        base_name_root = re.sub(r'SC\d+', scene.name, filename, flags=re.IGNORECASE)
    else:
        base_name_root = scene.name
        
    parts = base_name_root.split('_')
    if len(parts) > 1 and parts[-1].startswith('C') and any(c.isdigit() for c in parts[-1]):
        base_name_root = "_".join(parts[:-1])
        
    if scene.playblast_process == 'OTHERS':
        process_str = scene.playblast_process_custom
    else:
        process_str = scene.playblast_process.title()
        
    version_str = scene.playblast_version
    
    # Suffix placeholder (since camera suffix depends on markers during render)
    suffix = "_[Cam]"
    
    return f"{base_name_root}{suffix}_{process_str}_{version_str}.mp4"

class ANIM_OT_edit_playblast_note(bpy.types.Operator):
    """Open the Text Editor for the playblast note"""
    bl_idname = "anim.edit_playblast_note"
    bl_label = "Edit Note (Text Editor)"
    
    def execute(self, context):
        # 1. Get or create the Text Block
        text_name = "Playblast Note"
        text_block = bpy.data.texts.get(text_name)
        if not text_block:
            text_block = bpy.data.texts.new(name=text_name)
            # Pre-fill with existing scene note if any
            if context.scene.playblast_note:
                 text_block.write(context.scene.playblast_note)
        
        # 2. Open a new window
        bpy.ops.wm.window_new()
        
        # 3. Change area to Text Editor
        # The new window has one area, change it
        new_window = context.window_manager.windows[-1]
        area = new_window.screen.areas[0]
        area.type = 'TEXT_EDITOR'
        
        # 4. Assign the text block
        area.spaces[0].text = text_block
        
        return {'FINISHED'}

class ANIM_OT_auto_version(bpy.types.Operator):
    """Automatically set version to next available"""
    bl_idname = "anim.auto_version"
    bl_label = "Auto"
    
    def execute(self, context):
        scene = context.scene
        output_dir = bpy.path.abspath(scene.playblast_output_path)
        if not output_dir:
            output_dir = bpy.path.abspath("//Playblast/")
            
        if not os.path.exists(output_dir):
            self.report({'INFO'}, "Output folder doesn't exist yet, version 01 is robust.")
            scene.playblast_version = "01"
            return {'FINISHED'}
            
        # Scan for existing versions
        highest_ver = 0
        try:
            # Pattern to find _vXX or _XX at end of files
            # Simplified: just look for digits
            for f in os.listdir(output_dir):
                if not f.endswith(".mp4"): continue
                # Try to extract version number from end
                # Assuming format ..._v01.mp4 or ..._01.mp4
                match = re.search(r'_(\d+)\.mp4$', f, re.IGNORECASE)
                if match:
                    val = int(match.group(1))
                    if val > highest_ver:
                        highest_ver = val
                else:
                    # Try with 'v' prefix
                    match = re.search(r'[vV](\d+)\.mp4$', f)
                    if match:
                        val = int(match.group(1))
                        if val > highest_ver:
                            highest_ver = val
        except Exception as e:
            print(f"Auto-version error: {e}")
            
        next_ver = highest_ver + 1
        scene.playblast_version = f"{next_ver:02d}"
        self.report({'INFO'}, f"Version update to {scene.playblast_version}")
        return {'FINISHED'}

class ANIM_OT_playblast(bpy.types.Operator):
    """Render a playblast with metadata"""
    bl_idname = "anim.playblast"
    bl_label = "Playblast"
    bl_options = {'REGISTER'}

    # Property to store the name for display/use
    animator_name: bpy.props.StringProperty(default="Animator")

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        self.animator_name = get_animator_name()
        return context.window_manager.invoke_props_dialog(self, width=600)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Info Box
        box = layout.box()
        box.label(text=f"Frame Range: {scene.frame_start} - {scene.frame_end}", icon='TIME')
        
        # Settings
        col = layout.column()
        col.prop(scene, "playblast_process")
        if scene.playblast_process == 'OTHERS':
            col.prop(scene, "playblast_process_custom")
            
        # Version Row
        row = col.row(align=True)
        row.prop(scene, "playblast_version")
        row.operator("anim.auto_version", text="Auto Check", icon='FILE_REFRESH')
        
        col.separator()
        
        # Note Section
        row = col.row(align=True)
        row.label(text=f"Animator: {self.animator_name}")
        
        row = col.row(align=True)
        # Check if text block exists to show status
        text_block = bpy.data.texts.get("Playblast Note")
        
        # Note input (read-only ish or manual override)
        # We allow manual typing here too, which will get overwritten if Text Block is used
        row.prop(scene, "playblast_note", text="Note")
        
        # Button to open text editor
        icon = 'TEXT' if text_block else 'ADD'
        row.operator("anim.edit_playblast_note", text="", icon=icon)
        
        col.separator()
        
        # Preview
        box = layout.box()
        box.label(text="Filename Preview:", icon='FILE_TEXT')
        box.label(text=get_playblast_filename(scene))
        
        layout.label(text="Check settings before rendering!", icon='ERROR')

    def execute(self, context):
        scene = context.scene
        
        # Sync from Text Block to Scene Property first
        text_name = "Playblast Note"
        text_block = bpy.data.texts.get(text_name)
        if text_block:
            # Join lines with spaces or newlines? Metadata is single line usually.
            # Let's replace newlines with spaces for the stamp title
            content = text_block.as_string()
            # Clean up for stamp (single line)
            clean_content = content.replace('\n', ' ').strip()
            scene.playblast_note = clean_content
            
        # Combine config name and manual note
        animator_name = self.animator_name
        manual_note = scene.playblast_note
        
        # Format: "Animator: [Name] | [Note]"
        full_note = f"Animator: {animator_name}"
        if manual_note:
            full_note += f" | {manual_note}"
        print(f"DEBUG: Starting playblast execution. Scene: {scene.name}")

        # Store original settings
        original_filepath = scene.render.filepath
        original_stamp_info = scene.render.stamp_note_text
        original_use_stamp = scene.render.use_stamp
        original_stamp_font_size = scene.render.stamp_font_size
        original_file_format = scene.render.image_settings.file_format
        original_media_type = getattr(scene.render.image_settings, "media_type", None)
        original_ffmpeg_format = scene.render.ffmpeg.format
        original_ffmpeg_codec = scene.render.ffmpeg.codec
        original_use_file_extension = scene.render.use_file_extension
        original_frame_start = scene.frame_start
        original_frame_end = scene.frame_end
        original_camera = scene.camera

        # Store and Set Viewport settings
        original_shading_color = None
        original_wireframe_color = None
        if context.space_data and context.space_data.type == 'VIEW_3D':
            original_shading_color = context.space_data.shading.color_type
            original_wireframe_color = context.space_data.shading.wireframe_color_type
            
            context.space_data.shading.color_type = 'TEXTURE'
            context.space_data.shading.wireframe_color_type = 'THEME'

        # Set output path
        raw_path = scene.playblast_output_path
        if not raw_path:
            raw_path = "//Playblast/"
        output_dir = bpy.path.abspath(raw_path)
        
        print(f"DEBUG: Checking output dir: {output_dir}")
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except:
                self.report({'WARNING'}, f"Could not create output directory: {output_dir}")
                return {'CANCELLED'}

        # Determine base filename root
        if bpy.data.filepath:
            filename = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
            base_name_root = re.sub(r'SC\d+', scene.name, filename, flags=re.IGNORECASE)
        else:
            base_name_root = scene.name
        print(f"DEBUG: Base filename root determined: {base_name_root}")

        # Always clean up existing cut info from name (e.g. _C01)
        parts = base_name_root.split('_')
        if len(parts) > 1 and parts[-1].startswith('C') and any(c.isdigit() for c in parts[-1]):
            base_name_root = "_".join(parts[:-1])

        # Get Process and Version strings
        if scene.playblast_process == 'OTHERS':
            process_str = scene.playblast_process_custom
        else:
            process_str = scene.playblast_process.title() # e.g. "Blocking"
        
        version_str = scene.playblast_version

        # Define render tasks
        render_tasks = []
        # Force use of markers
        all_markers = scene.timeline_markers
        markers = [m for m in sorted(all_markers, key=lambda m: m.frame) if original_frame_start <= m.frame <= original_frame_end and m.camera]
        print(f"DEBUG: Found {len(markers)} bound markers (ignored {len(all_markers) - len(markers)} unbound/out-of-range).")

        if markers:
            # Track camera usage to handle duplicates
            cam_usage = {}

            for i, marker in enumerate(markers):
                start = marker.frame
                if i < len(markers) - 1:
                    end = markers[i+1].frame - 1
                else:
                    end = original_frame_end
                
                if end >= start:
                    cam_name = marker.camera.name
                    count = cam_usage.get(cam_name, 0) + 1
                    cam_usage[cam_name] = count
                    
                    suffix = f"_{cam_name}"
                    if count > 1:
                        suffix += f"_{count:02d}"

                    print(f"DEBUG: Marker bound to camera '{marker.camera.name}'. Suffix: '{suffix}' ({start}-{end})")
                    render_tasks.append({
                        "start": start,
                        "end": end,
                        "suffix": suffix,
                        "camera": marker.camera
                    })
        else:
            # Fallback if no markers found: Render whole range as C01
            suffix = f"_{scene.camera.name}" if scene.camera else "_C01"
            print(f"DEBUG: No markers. Fallback task: {suffix}")
            render_tasks.append({"start": original_frame_start, "end": original_frame_end, "suffix": suffix, "camera": scene.camera})

        # Set format to MPEG-4 H.264
        try:
            scene.render.image_settings.media_type = 'VIDEO'
        except AttributeError:
            pass
        scene.render.ffmpeg.format = 'MPEG4'
        scene.render.ffmpeg.codec = 'H264'

        # Set metadata
        scene.render.use_stamp = True
        scene.render.stamp_font_size = 24
        scene.render.use_stamp_note = True
        scene.render.stamp_note_text = full_note
        scene.render.use_stamp_date = True
        scene.render.use_stamp_time = True
        scene.render.use_stamp_frame = True
        scene.render.use_stamp_camera = True
        scene.render.use_stamp_lens = True
        scene.render.use_stamp_scene = True
        scene.render.use_stamp_filename = True
        scene.render.use_stamp_marker = True

        
        # Execute Renders
        for task in render_tasks:
            scene.frame_start = task["start"]
            scene.frame_end = task["end"]
            
            if task.get("camera"):
                scene.camera = task["camera"]
            
            # Filename logic
            filename = f"{base_name_root}{task['suffix']}_{process_str}_{version_str}"
            print(f"DEBUG: Rendering: {filename}")
            
            # Check for conflicts and increment if necessary
            base_filename = filename
            counter = 1
            while os.path.exists(os.path.join(output_dir, filename + ".mp4")):
                filename = f"{base_filename}.{counter:03d}"
                counter += 1

            scene.render.filepath = os.path.join(output_dir, filename + ".mp4")
            scene.render.use_file_extension = False

            # Render
            bpy.ops.render.opengl(animation=True)

        if len(render_tasks) == 1:
            bpy.ops.render.play_rendered_anim()

        # Restore original settings
        scene.frame_start = original_frame_start
        scene.frame_end = original_frame_end
        scene.camera = original_camera
        scene.render.filepath = original_filepath
        scene.render.stamp_note_text = original_stamp_info
        scene.render.use_stamp = original_use_stamp
        scene.render.stamp_font_size = original_stamp_font_size
        scene.render.image_settings.media_type = 'VIDEO'

        if original_media_type:
            scene.render.image_settings.media_type = original_media_type
        scene.render.image_settings.file_format = original_file_format
        scene.render.ffmpeg.format = original_ffmpeg_format
        scene.render.ffmpeg.codec = original_ffmpeg_codec
        scene.render.use_file_extension = original_use_file_extension

        # Restore Viewport settings
        if original_shading_color:
            context.space_data.shading.color_type = original_shading_color
        if original_wireframe_color:
            context.space_data.shading.wireframe_color_type = original_wireframe_color

        return {'FINISHED'}
