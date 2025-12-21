
import bpy
import os
import re

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
        output_dir = r"X:\My Drive\50_Render_Output\00_Blender\Playblast"
        print(f"DEBUG: Checking output dir: {output_dir}")
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except:
                self.report({'WARNING'}, f"Output not found เช็ค Google drive!!!: {output_dir}")
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
