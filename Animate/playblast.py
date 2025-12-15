
import bpy
import os

class ANIM_OT_playblast(bpy.types.Operator):
    """Render a playblast with metadata"""
    bl_idname = "anim.playblast"
    bl_label = "Playblast"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=200)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.label(text=f"Frame Range: {scene.frame_start} - {scene.frame_end} ?")
        layout.label(text="Please check the settings.")
        layout.prop(scene, "playblast_process")
        if scene.playblast_process == 'OTHERS':
            layout.prop(scene, "playblast_process_custom")
        layout.prop(scene, "playblast_version")
        layout.prop(scene, "playblast_note", text="Animator ")
        layout.label(text="ถูกไหม?เช็คดีๆนะๆๆๆ")

    def execute(self, context):
        scene = context.scene
        note = scene.playblast_note

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

        # Set output path
        output_dir = r"X:\My Drive\50_Render_Output\00_Blender\Playblast"
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except:
                self.report({'WARNING'}, f"Output not found เช็ค Google drive!!!: {output_dir}")
                return {'CANCELLED'}

        # Determine base filename root
        if bpy.data.filepath:
            base_name_root = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
            # Always clean up existing cut info from filename (e.g. _C01)
            parts = base_name_root.split('_')
            if len(parts) > 1 and parts[-1].startswith('C') and any(c.isdigit() for c in parts[-1]):
                base_name_root = "_".join(parts[:-1])
        else:
            base_name_root = "Playblast"

        # Get Process and Version strings
        if scene.playblast_process == 'OTHERS':
            process_str = scene.playblast_process_custom
        else:
            process_str = scene.playblast_process.title() # e.g. "Blocking"
        
        version_str = scene.playblast_version

        # Define render tasks
        render_tasks = []
        # Force use of markers
        markers = [m for m in sorted(scene.timeline_markers, key=lambda m: m.frame) if original_frame_start <= m.frame <= original_frame_end]

        if markers:
            for i, marker in enumerate(markers):
                start = marker.frame
                if i < len(markers) - 1:
                    end = markers[i+1].frame - 1
                else:
                    end = original_frame_end
                
                if end >= start:
                    render_tasks.append({
                        "start": start,
                        "end": end,
                        "suffix": f"_C{i+1:02d}"
                    })
        else:
            # Fallback if no markers found: Render whole range as C01
            render_tasks.append({"start": original_frame_start, "end": original_frame_end, "suffix": "_C01"})

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
        scene.render.stamp_note_text = f"Animator: {note}"
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
            
            # Filename logic
            filename = f"{base_name_root}{task['suffix']}_{process_str}_{version_str}"
            
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
        scene.render.filepath = original_filepath
        scene.render.stamp_note_text = original_stamp_info
        scene.render.use_stamp = original_use_stamp
        scene.render.stamp_font_size = original_stamp_font_size
        scene.render.image_settings.media_type = 'VIDEO'
        #Stupid Ass Gemini
        
        if original_media_type:
            scene.render.image_settings.media_type = original_media_type
        scene.render.image_settings.file_format = original_file_format
        scene.render.ffmpeg.format = original_ffmpeg_format
        scene.render.ffmpeg.codec = original_ffmpeg_codec
        scene.render.use_file_extension = original_use_file_extension

        return {'FINISHED'}
