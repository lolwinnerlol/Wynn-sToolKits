import bpy
import gpu
import gpu_extras.batch
from bpy.props import IntProperty, BoolProperty, FloatProperty, EnumProperty, PointerProperty, FloatVectorProperty
from mathutils import Matrix, Vector

# Global storage for GPU resources (since PropertyGroups are recreated)
OFFSCREEN_CACHE = {}  # Key: str(screen_pointer) or screen.name -> GPUOffScreen

# -------------------------------------------------------------------
#   Properties
# -------------------------------------------------------------------

class Camera_Viewer_Props(bpy.types.PropertyGroup):
    """Properties for the Picture-in-Picture logic (attached to Screen)"""
    
    is_active: BoolProperty(
        name="Viewer Active",
        default=False,
        description="Master switch for the Camera Viewer"
    )
    
    # Position and Size
    pos_x: IntProperty(default=50, name="Position X")
    pos_y: IntProperty(default=50, name="Position Y")
    width: IntProperty(default=400, min=100, name="Width")
    height: IntProperty(default=300, min=100, name="Height")
    
    # Navigation / Interaction state
    is_dragging: BoolProperty(default=False)
    is_resizing: BoolProperty(default=False)
    
    # Settings
    scale: FloatProperty(default=1.0, min=0.1, max=2.0, name="Quality Scale")

class Camera_Viewer_UI_Props(bpy.types.PropertyGroup):
    """UI State properties (attached to Scene or Screen)"""
    show_gizmos: BoolProperty(default=True)


# -------------------------------------------------------------------
#   Shader & Rendering
# -------------------------------------------------------------------

def get_shader():
    """Returns the GLSL shader for drawing the offscreen texture."""
    # Simple 2D texture shader
    shader_info = gpu.types.GPUShaderCreateInfo()
    shader_info.push_constant('mat4', "ModelViewProjectionMatrix")
    shader_info.push_constant('sampler2D', "image")
    shader_info.vertex_source(
        "void main() {"
        "  gl_Position = ModelViewProjectionMatrix * vec4(pos, 0.0, 1.0);"
        "  texCoord = texCmd;"
        "}"
    )
    shader_info.fragment_source(
        "void main() {"
        "  fragColor = texture(image, texCoord);"
        "}"
    )
    
    # Attributes
    shader_info.vertex_in(0, 'UNIFORM', 'vec2', 'pos')
    shader_info.vertex_in(1, 'UNIFORM', 'vec2', 'texCmd')
    
    try:
        return gpu.shader.from_builtin('IMAGE')
    except Exception:
        # Fallback for older versions or if 2D_IMAGE isn't exactly what we want
        pass
        
    return gpu.shader.create_from_info(shader_info)

_draw_handle = None
_shader = None

def get_offscreen(screen_name, width, height):
    """Manages the GPUOffScreen buffer globally."""
    global OFFSCREEN_CACHE
    
    offscreen = OFFSCREEN_CACHE.get(screen_name)
    
    if offscreen:
        if (offscreen.width != width or 
            offscreen.height != height):
            offscreen = None
            # Old one will be GC'd or we should explicitly close it?
            # Usually GC is fine but explicit is better for VRAM.
            # However we lost the ref in cache, so just overwrite.
            # If we want to be safe:
            # OFFSCREEN_CACHE[screen_name].free() # if free exists? 
            # GPUOffScreen doesn't usually expose explicit free easily in Py API
            # besides just losing ref.
            
    if not offscreen:
        try:
            offscreen = gpu.types.GPUOffScreen(width, height)
            OFFSCREEN_CACHE[screen_name] = offscreen
        except Exception as e:
            print(f"Failed to create GPUOffScreen: {e}")
            return None
            
    return offscreen

def cleanup_offscreens_cache():
    global OFFSCREEN_CACHE
    OFFSCREEN_CACHE.clear()

# -------------------------------------------------------------------
#   Shadow Screen Management
# -------------------------------------------------------------------

def get_shadow_screen_name(base_screen):
    name = base_screen.name
    if name.endswith(" Shadow"):
        return name
    return f"{name} Shadow"

def find_shadow_screen(context):
    """Safely finds the shadow screen without modifying context."""
    base_screen = context.screen
    name = get_shadow_screen_name(base_screen)
    found = bpy.data.screens.get(name)
    if not found:
        print(f"DEBUG: find_shadow_screen looking for '{name}' but not found. Available: {[s.name for s in bpy.data.screens if 'Shadow' in s.name]}")
    return found

def create_shadow_screen(context):
    """Creates the independent shadow screen. MUST be called from Operator, NOT Draw Handler."""
    base_screen = context.screen
    name = get_shadow_screen_name(base_screen)
    
    shadow_screen = bpy.data.screens.get(name)
    
    shadow_screen = bpy.data.screens.get(name)
    
    if not shadow_screen:
        # Strategy: Use bpy.ops.screen.new() but detect the new screen via list comparison
        # This avoids assuming context switch and avoids the crashy .copy() API
        
        existing_screens = set(bpy.data.screens)
        prev_screen = context.window.screen
        
        try:
            retval = bpy.ops.screen.new()
            
            # Identify the new screen
            # If context switched, it's the active one.
            if context.window.screen != prev_screen:
                shadow_screen = context.window.screen
            else:
                # If context didn't switch, check diff
                new_screens = set(bpy.data.screens) - existing_screens
                if new_screens:
                    shadow_screen = new_screens.pop()
                else:
                    print("ERROR: bpy.ops.screen.new() finished but no new screen found.")
                    return None
            
            shadow_screen.name = name
            print(f"DEBUG: Created shadow screen '{name}' (Method: Ops Diff).")
            
        except Exception as e:
            print(f"ERROR: Failed to create shadow screen: {e}")
            return None
        finally:
            # CRITICAL: Always restore the original screen
            current_name = context.window.screen.name
            target_name = prev_screen.name
            print(f"DEBUG: Finally block. Current: '{current_name}', Target: '{target_name}'")
            
            # Force restore
            context.window.screen = prev_screen
            
            # Verify
            if context.window.screen != prev_screen:
                 print(f"CRITICAL ERROR: Failed to restore screen! Stuck on '{context.window.screen.name}'")
            else:
                 print(f"DEBUG: Successfully restored active screen to '{prev_screen.name}'")
            
    # Get Preferences
    addon_name = __package__.split(".")[0]
    prefs = context.preferences.addons[addon_name].preferences
    
    # Always enforce settings (in case they were changed or it's a reuse)
    if shadow_screen:
         for area in shadow_screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        # SETUP SILHOUETTE SHADING
                        space.shading.type = 'SOLID'
                        space.shading.light = 'FLAT'
                        space.shading.color_type = 'SINGLE'
                        space.shading.single_color = prefs.silhouette_color
                        
                        space.shading.background_type = 'VIEWPORT'
                        space.shading.background_color = prefs.background_color
                        
                        space.overlay.show_overlays = False
                        
    return shadow_screen

def cleanup_shadow_screens():
    """Removes any shadow screens to clean up."""
    to_remove = []
    for screen in bpy.data.screens:
        if screen.name.endswith(" Shadow"):
            to_remove.append(screen)
            
    for screen in to_remove:
        bpy.data.screens.remove(screen)


# -------------------------------------------------------------------
#   Draw Handler
# -------------------------------------------------------------------

def draw_callback_px():
    """The main drawing function for the viewport overlay."""
    context = bpy.context
    if not hasattr(context, "screen") or not context.screen:
        return
        
    props = context.screen.camera_viewer_props
    if not props.is_active:
        return
        
    region = context.region
    
    # 1. Setup Offscreen
    try:
        w = int(props.width * props.scale)
        h = int(props.height * props.scale)
        if w < 1: w = 1
        if h < 1: h = 1
        
        # Use screen name as key unique to this workspace/window usually
        offscreen = get_offscreen(context.screen.name, w, h)
        if not offscreen:
            return
            
    except Exception as e:
        print(f"DEBUG: Failed in offscreen setup: {e}")
        return
        
    # 2. Find/Setup Shadow Context
    shadow_screen = find_shadow_screen(context)
    if not shadow_screen:
        return
        
    if shadow_screen == context.screen:
        print("CRITICAL WARNING: Shadow Screen is the SAME as Active Screen! Isolation failed.")
        
    # Find a valid 3D view in shadow screen
    shadow_space = None
    shadow_region = None
    
    for area in shadow_screen.areas:
        if area.type == 'VIEW_3D':
            shadow_space = area.spaces.active
            for reg in area.regions:
                if reg.type == 'WINDOW':
                    shadow_region = reg
            break
            
    if not shadow_space or not shadow_region:
        return

    # 3. Offscreen Draw
    scene = context.scene
    camera = scene.camera
    
    view_matrix = None
    projection_matrix = None
    
    if camera:
        render = scene.render
        view_matrix = camera.matrix_world.inverted()
        projection_matrix = camera.calc_matrix_camera(
            context.evaluated_depsgraph_get(),
            x=w, y=h,
            scale_x=render.pixel_aspect_x,
            scale_y=render.pixel_aspect_y,
        )
    else:
        return

    # Unbind offscreen before drawing to it to be safe (though draw_view3d handles it)
    # offscreen.unbind() 
    
    # 4. Draw 3D View to Offscreen
    try:
        # Reverting 'None' to 'context.region' as 'None' likely causes blank output.
        # Now that Screen Isolation is fixed (Context Restoration), we hope Space shading is respected.
        offscreen.draw_view3d(
            scene,
            context.view_layer,
            shadow_space, 
            context.region, 
            view_matrix,
            projection_matrix,
            do_color_management=True
        )
    except Exception as e:
        print(f"Error drawing offscreen: {e}")
        return
    
    # 4. Draw Texture to Screen
    gpu.state.blend_set('ALPHA')
    try:
        shader = gpu.shader.from_builtin('IMAGE')
    except:
        shader = gpu.shader.from_builtin('2D_IMAGE')
    
    gpu.matrix.push()
    gpu.matrix.load_identity()
    
    x, y = props.pos_x, props.pos_y
    
    batch = gpu_extras.batch.batch_for_shader(
        shader, 'TRI_FAN',
        {
            "pos": ((x, y), (x + props.width, y), (x + props.width, y + props.height), (x, y + props.height)),
            "texCoord": ((0, 0), (1, 0), (1, 1), (0, 1)),
        },
    )
    
    shader.bind()
    shader.uniform_sampler("image", offscreen.texture_color)
    batch.draw(shader)
    
    # Draw Border
    try:
        shader_uc = gpu.shader.from_builtin('UNIFORM_COLOR')
    except:
        shader_uc = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
        
    batch_border = gpu_extras.batch.batch_for_shader(
        shader_uc, 'LINE_LOOP',
        {
            "pos": ((x, y), (x + props.width, y), (x + props.width, y + props.height), (x, y + props.height)),
        },
    )
    shader_uc.bind()
    shader_uc.uniform_float("color", (1.0, 1.0, 1.0, 0.5))
    batch_border.draw(shader_uc)
    
    gpu.matrix.pop()
    gpu.state.blend_set('NONE')
    



# -------------------------------------------------------------------
#   Operators
# -------------------------------------------------------------------

class WYNN_OT_OpenSilhouetteWindow(bpy.types.Operator):
    """Toggle the Camera Viewer (Silhouette PiP)"""
    bl_idname = "wynn.open_silhouette_window"
    bl_label = "Toggle Silhouette Window"
    
    def execute(self, context):
        props = context.screen.camera_viewer_props
        props.is_active = not props.is_active
        
        if props.is_active:
             create_shadow_screen(context)
             
        context.area.tag_redraw()
        return {'FINISHED'}

class WYNN_OT_modify_camera_viewer(bpy.types.Operator):
    """Move and Resize the Camera Viewer"""
    bl_idname = "wynn.modify_camera_viewer"
    bl_label = "Modify Viewer"
    bl_options = {'BLOCKING', 'GRAB_CURSOR'}
    
    action: EnumProperty(
        items=[
            ('MOVE', "Move", ""),
            ('RESIZE', "Resize", ""),
        ]
    )
    
    _init_mx = 0; _init_my = 0
    _init_x = 0; _init_y = 0
    _init_w = 0; _init_h = 0
    
    def modal(self, context, event):
        props = context.screen.camera_viewer_props
        
        if event.type == 'MOUSEMOVE':
            dx = event.mouse_region_x - self._init_mx
            dy = event.mouse_region_y - self._init_my
            
            if self.action == 'MOVE':
                props.pos_x = self._init_x + dx
                props.pos_y = self._init_y + dy
            elif self.action == 'RESIZE':
                props.width = max(100, self._init_w + dx)
                props.height = max(100, self._init_h + dy)
            context.area.tag_redraw()
        
        elif event.type in {'LEFTMOUSE', 'ENTER'}:
            props.is_dragging = False
            props.is_resizing = False
            return {'FINISHED'}
            
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            props.is_dragging = False
            props.is_resizing = False
            return {'CANCELLED'}
            
        return {'RUNNING_MODAL'}
    
    def invoke(self, context, event):
        props = context.screen.camera_viewer_props
        self._init_mx = event.mouse_region_x
        self._init_my = event.mouse_region_y
        self._init_x = props.pos_x
        self._init_y = props.pos_y
        self._init_w = props.width
        self._init_h = props.height
        
        if self.action == 'MOVE': props.is_dragging = True
        elif self.action == 'RESIZE': props.is_resizing = True
            
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

class WYNN_OT_Navigation_Camera_Viewer(bpy.types.Operator):
    """Fly Navigation for Camera Viewer"""
    bl_idname = "wynn.navigation_camera_viewer"
    bl_label = "Navigate Camera"
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}

    first_mouse_x: IntProperty()
    first_mouse_y: IntProperty()
    
    _key_state = set()
    _timer = None
    
    def modal(self, context, event):
        scene = context.scene
        camera = scene.camera
        if not camera:
            return {'CANCELLED'}
        
        # KEY HANDLING
        if event.value == 'PRESS':
            self._key_state.add(event.type)
        elif event.value == 'RELEASE':
            if event.type in self._key_state:
                self._key_state.remove(event.type)
                
        # Handle Timer for Smooth Movement
        if event.type == 'TIMER':
            dt = 0.05 # Fixed step from timer
            speed = 5.0 * dt # Meters per second approx
            
            # Speed Boost
            if 'LEFT_SHIFT' in self._key_state:
                speed *= 3.0
            
            move_vec = Vector((0, 0, 0))
            if 'W' in self._key_state: move_vec.z -= 1
            if 'S' in self._key_state: move_vec.z += 1
            if 'A' in self._key_state: move_vec.x -= 1
            if 'D' in self._key_state: move_vec.x += 1
            if 'Q' in self._key_state: move_vec.y -= 1
            if 'E' in self._key_state: move_vec.y += 1
            
            if move_vec.length > 0:
                mat = camera.matrix_world.to_3x3()
                global_move = mat @ move_vec
                camera.location += global_move * speed
                
            context.area.tag_redraw()

        # MOUSE LOOK
        if event.type == 'MOUSEMOVE':
            dx = event.mouse_region_x - self.first_mouse_x
            dy = event.mouse_region_y - self.first_mouse_y
            
            # Wrap Cursor
            # (Optional: for now just clamp or direct mapping)
            # context.window.warp_cursor(...)
            
            sens = 0.005
            
            # Pan (Global Z)
            rot_z = Matrix.Rotation(-dx * sens, 4, 'Z')
            camera.matrix_world = rot_z @ camera.matrix_world
            
            # Tilt (Local X)
            rot_x = Matrix.Rotation(-dy * sens, 4, 'X')
            camera.matrix_world = camera.matrix_world @ rot_x
            
            # Reset
            self.first_mouse_x = event.mouse_region_x
            self.first_mouse_y = event.mouse_region_y
            
        if event.type in {'ESC', 'RIGHTMOUSE'}:
            self.finish(context)
            return {'FINISHED'}
            
        return {'RUNNING_MODAL'}
        
    def invoke(self, context, event):
        self.first_mouse_x = event.mouse_region_x
        self.first_mouse_y = event.mouse_region_y
        self._key_state = set()
        
        if not context.scene.camera:
            self.report({'ERROR'}, "No active camera")
            return {'CANCELLED'}
            
        context.window_manager.modal_handler_add(self)
        self._timer = context.window_manager.event_timer_add(0.016, window=context.window)
        return {'RUNNING_MODAL'}
        
    def finish(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None

# -------------------------------------------------------------------
#   UI Panel
# -------------------------------------------------------------------

# -------------------------------------------------------------------
#   UI Drawing Helper (Called from __init__.py)
# -------------------------------------------------------------------

def draw_camera_viewer_ui(layout, context):
    """Draws the Camera Viewer settings. Call this from the main panel."""
    # We access the properties on the current screen
    if not hasattr(context, "screen") or not context.screen:
        return

    props = context.screen.camera_viewer_props
    
    # Check if we should only show settings if active? 
    # The Toggle Button is usually drawn by the parent panel, but let's see.
    # The parent panel draws "wynn.open_silhouette_window" operator.
    # But that operator just toggles `props.is_active`.
    # So we can show the settings if `props.is_active`.
    
    if props.is_active:
        box = layout.box()
        box.label(text="Camera Window Settings", icon='PREFERENCES')
        
        col = box.column(align=True)
        col.label(text="Position:")
        row = col.row(align=True)
        row.prop(props, "pos_x", text="X")
        row.prop(props, "pos_y", text="Y")
        
        col.separator()
        col.label(text="Dimensions:")
        row = col.row(align=True)
        row.prop(props, "width", text="W")
        row.prop(props, "height", text="H")
        
        col.separator()
        col.prop(props, "scale", slider=True)

# -------------------------------------------------------------------
#   Gizmos
# -------------------------------------------------------------------

class CameraViewerGizmoGroup(bpy.types.GizmoGroup):
    bl_idname = "VIEW3D_GGT_camera_viewer"
    bl_label = "Camera Viewer Widgets"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}

    @classmethod
    def poll(cls, context):
        if not hasattr(context.screen, "camera_viewer_props"): return False
        return context.screen.camera_viewer_props.is_active

    def setup(self, context):
        # Resize Handle
        gz = self.gizmos.new("GIZMO_GT_button_2d")
        gz.icon = 'ARROW_LEFTRIGHT'
        gz.draw_options = {'BACKDROP', 'OUTLINE'}
        gz.color = 0.8, 0.8, 0.8
        gz.alpha = 0.5
        gz.color_highlight = 1.0, 1.0, 1.0
        
        props = gz.target_set_operator("wynn.modify_camera_viewer")
        props.action = 'RESIZE'
        self.gz_resize = gz
        
        # Move Handle
        gz = self.gizmos.new("GIZMO_GT_button_2d")
        gz.draw_options = {'BACKDROP', 'OUTLINE'}
        gz.icon = 'VIEW_PAN'
        props = gz.target_set_operator("wynn.modify_camera_viewer")
        props.action = 'MOVE'
        self.gz_move = gz
        
        # Nav Handle
        gz = self.gizmos.new("GIZMO_GT_button_2d")
        gz.draw_options = {'BACKDROP', 'OUTLINE'}
        gz.icon = 'VIEW3D'
        gz.target_set_operator("wynn.navigation_camera_viewer")
        self.gz_nav = gz

    def draw_prepare(self, context):
        props = context.screen.camera_viewer_props
        
        x, y = props.pos_x, props.pos_y
        w, h = props.width, props.height
        
        # Resize at Top-Right
        self.gz_resize.matrix_basis[0][3] = x + w
        self.gz_resize.matrix_basis[1][3] = y + h
        
        # Move at Center
        self.gz_move.matrix_basis[0][3] = x + (w / 2)
        self.gz_move.matrix_basis[1][3] = y + h - 20 # Top bar
        
        # Nav at Top-Left
        self.gz_nav.matrix_basis[0][3] = x + 20
        self.gz_nav.matrix_basis[1][3] = y + h - 20


# -------------------------------------------------------------------
#   Registration
# -------------------------------------------------------------------

classes = (
    Camera_Viewer_Props,
    Camera_Viewer_UI_Props,
    WYNN_OT_OpenSilhouetteWindow,
    WYNN_OT_modify_camera_viewer,
    WYNN_OT_Navigation_Camera_Viewer,
    CameraViewerGizmoGroup,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
        
    bpy.types.Screen.camera_viewer_props = PointerProperty(type=Camera_Viewer_Props)
    
    global _draw_handle
    if _draw_handle is None:
        _draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            draw_callback_px, (), 'WINDOW', 'POST_PIXEL'
        )

def unregister():
    global _draw_handle
    if _draw_handle:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, 'WINDOW')
        _draw_handle = None

    if hasattr(bpy.types.Screen, "camera_viewer_props"):
        del bpy.types.Screen.camera_viewer_props
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
        
    cleanup_shadow_screens()
    cleanup_offscreens_cache()
