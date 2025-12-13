
import bpy

class ANIM_OT_playblast(bpy.types.Operator):
    """Render a playblast with metadata"""
    bl_idname = "anim.playblast"
    bl_label = "Playblast"

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        scene = context.scene
        note = scene.playblast_note

        # Store original settings
        original_stamp_info = scene.render.stamp_note_text
        original_use_stamp = scene.render.use_stamp
        original_stamp_font_size = scene.render.stamp_font_size

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

        # Restore original settings
        scene.render.stamp_note_text = original_stamp_info
        scene.render.use_stamp = original_use_stamp
        scene.render.stamp_font_size = original_stamp_font_size

        bpy.ops.render.play_rendered_anim()

        return {'FINISHED'}
