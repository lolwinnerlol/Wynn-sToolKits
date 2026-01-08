import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from bpy.props import IntProperty, BoolProperty
from mathutils import Matrix


class WYNN_OT_OpenSilhouetteWindow(bpy.types.Operator):
    bl_idname = "wynn.open_silhouette_window"
    bl_label = "Open Silhouette Window"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        self.report({'INFO'}, "Silhouette window opened")
        return {'FINISHED'}

    _handle = None

    # Window geometry
    pos_x: IntProperty(default=50)
    pos_y: IntProperty(default=50)
    width: IntProperty(default=300)
    height: IntProperty(default=300)

    # Interaction state
    dragging: BoolProperty(default=False)
    resizing: BoolProperty(default=False)

    drag_start_x: IntProperty()
    drag_start_y: IntProperty()
    start_x: IntProperty()
    start_y: IntProperty()
    start_w: IntProperty()
    start_h: IntProperty()

    # ------------------------
    # DRAW
    # ------------------------

    def draw_callback(self, context):
        region = context.region
        if not region:
            return

        gpu.matrix.push()

        # Correct orthographic projection for POST_PIXEL (Blender 5.0)
        proj = Matrix.Ortho(
            0, region.width,
            0, region.height,
            -1.0, 1.0
        )
        gpu.matrix.load_projection_matrix(proj)
        gpu.matrix.load_model_view_matrix(Matrix.Identity(4))

        shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')

        # Main window quad
        batch = batch_for_shader(
            shader, 'TRI_FAN',
            {
                "pos": (
                    (self.pos_x, self.pos_y),
                    (self.pos_x + self.width, self.pos_y),
                    (self.pos_x + self.width, self.pos_y + self.height),
                    (self.pos_x, self.pos_y + self.height),
                )
            }
        )

        shader.bind()
        shader.uniform_float("color", (0.05, 0.05, 0.05, 0.9))
        gpu.state.blend_set('ALPHA')
        batch.draw(shader)

        # Resize corner
        c = 16
        corner = batch_for_shader(
            shader, 'TRI_FAN',
            {
                "pos": (
                    (self.pos_x + self.width - c, self.pos_y + self.height - c),
                    (self.pos_x + self.width, self.pos_y + self.height - c),
                    (self.pos_x + self.width, self.pos_y + self.height),
                    (self.pos_x + self.width - c, self.pos_y + self.height),
                )
            }
        )
        shader.uniform_float("color", (1, 1, 1, 1))
        corner.draw(shader)

        gpu.state.blend_set('NONE')
        gpu.matrix.pop()

    # ------------------------
    # MODAL
    # ------------------------

    def modal(self, context, event):
        context.area.tag_redraw()

        mx, my = event.mouse_region_x, event.mouse_region_y

        in_rect = (
            self.pos_x < mx < self.pos_x + self.width and
            self.pos_y < my < self.pos_y + self.height
        )

        c = 16
        in_corner = (
            self.pos_x + self.width - c < mx < self.pos_x + self.width and
            self.pos_y + self.height - c < my < self.pos_y + self.height
        )

        if event.type in {'ESC', 'RIGHTMOUSE'}:
            self.finish()
            return {'CANCELLED'}

        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                if in_corner:
                    self.resizing = True
                    self.drag_start_x = mx
                    self.drag_start_y = my
                    self.start_w = self.width
                    self.start_h = self.height
                elif in_rect:
                    self.dragging = True
                    self.drag_start_x = mx
                    self.drag_start_y = my
                    self.start_x = self.pos_x
                    self.start_y = self.pos_y

            elif event.value == 'RELEASE':
                self.dragging = False
                self.resizing = False

        if event.type == 'MOUSEMOVE':
            if self.dragging:
                self.pos_x = self.start_x + (mx - self.drag_start_x)
                self.pos_y = self.start_y + (my - self.drag_start_y)
            elif self.resizing:
                self.width = max(80, self.start_w + (mx - self.drag_start_x))
                self.height = max(80, self.start_h + (my - self.drag_start_y))

        return {'PASS_THROUGH'}

    # ------------------------
    # INVOKE / CLEANUP
    # ------------------------

    def invoke(self, context, event):
        if context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Must be run in 3D View")
            return {'CANCELLED'}

        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_callback, (context,), 'WINDOW', 'POST_PIXEL'
        )
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def finish(self):
        if self._handle:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            self._handle = None


# ------------------------
# REGISTRATION (module-safe)
# ------------------------

def register():
    bpy.utils.register_class(WYNN_OT_OpenSilhouetteWindow)


def unregister():
    bpy.utils.unregister_class(WYNN_OT_OpenSilhouetteWindow)
