
import bpy
import os

class ANIM_OT_playblast(bpy.types.Operator):
    """Render a playblast with metadata"""
    bl_idname = "anim.playblast"
    bl_label = "Playblast"

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=200)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Render Playblast?")

    def execute(self, context):
        scene = context.scene
        note = scene.playblast_note
        shot_name = scene.playblast_shot_name

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

        # Set output path
        output_dir = r"X:\My Drive\50_Render_Output\00_Blender\Playblast"
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except:
                pass # Drive might not exist or be accessible

        filename = shot_name if shot_name else "Playblast"

        # Check for conflicts and increment if necessary
        base_filename = filename
        counter = 1
        while os.path.exists(os.path.join(output_dir, filename + ".mp4")):
            filename = f"{base_filename}.{counter:03d}"
            counter += 1

        scene.render.filepath = os.path.join(output_dir, filename + ".mp4")
        scene.render.use_file_extension = False

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
        
        # Render
        bpy.ops.render.opengl(animation=True)

        bpy.ops.render.play_rendered_anim()

        # Restore original settings
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
