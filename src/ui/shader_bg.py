from pathlib import Path
from ctypes import c_void_p, c_float, c_uint, CDLL
import sys
from PyQt6.QtCore import QTimer
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from src.common.vars import log

# try:
from OpenGL.GL import *
from OpenGL.GL.shaders import compileShader, compileProgram

import ctypes.util

if sys.platform == "win32":
    libgl = CDLL("opengl32.dll")
    # On windows for some reason opengl functions get loaded in the global space and not libgl variable, whatever...
    _glVertexAttribPointer = glVertexAttribPointer
    _glEnableVertexAttribArray = glEnableVertexAttribArray
else:
    libgl_path = ctypes.util.find_library("GL")
    if not libgl_path:
        raise ImportError("Cannot find OpenGL library")
    libgl = CDLL(libgl_path)
    _glVertexAttribPointer = libgl.glVertexAttribPointer
    _glEnableVertexAttribArray = libgl.glEnableVertexAttribArray

    _glVertexAttribPointer.argtypes = [c_uint, c_uint, c_uint, c_uint, c_uint, c_void_p]
    _glVertexAttribPointer.restype = None

    _glEnableVertexAttribArray.argtypes = [c_uint]
    _glEnableVertexAttribArray.restype = None

    OPENGL_AVAILABLE = True
# except ImportError:
# OPENGL_AVAILABLE = False
# log("OpenGL not available you dont have graphics?")


class OpenGLBackground(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._initialized = False
        self._main_program = None
        self._vao: int = 0
        self._vbo: int = 0
        self._time: float = 0.0
        self._noise_texture: int = 0
        self._brightness: float = 0.9

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_time)

    def set_brightness(self, brightness: float):
        self._brightness = max(0.0, min(1.0, brightness))
        self.update()

    def initializeGL(self):
        if not OPENGL_AVAILABLE:
            log("OpenGL not available")
            return

        try:
            self.makeCurrent()

            version = glGetString(GL_VERSION)
            if version:
                log(f"OpenGL initialized: {version.decode()}")

            vertex_src = self._load_shader("background/vertex.glsl")
            fragment_src = self._load_shader("background/fragment.glsl")

            if not vertex_src or not fragment_src:
                log("Failed to load shaders")
                return

            vs = compileShader(vertex_src, GL_VERTEX_SHADER)
            fs = compileShader(fragment_src, GL_FRAGMENT_SHADER)
            self._main_program = compileProgram(vs, fs)

            vertices = (c_float * 12)(
                -1.0, -1.0, 0.0, 1.0, -1.0, 0.0, -1.0, 1.0, 0.0, 1.0, 1.0, 0.0
            )

            self._vao = glGenVertexArrays(1)
            glBindVertexArray(self._vao)

            self._vbo = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
            glBufferData(GL_ARRAY_BUFFER, len(vertices) * 4, vertices, GL_STATIC_DRAW)

            _glEnableVertexAttribArray(0)
            _glVertexAttribPointer(0, 3, 0x1406, 0, 12, None)

            glBindVertexArray(0)

            self._create_noise_texture()

            self._initialized = True
            self._timer.start(16)

            log("OpenGL background initialized successfully")

        except Exception as e:
            log(f"OpenGL init error: {e}")
            import traceback

            log(traceback.format_exc())

    def _load_shader(self, path: str) -> str:
        try:
            shader_path = Path(path)
            if not shader_path.exists():
                log(f"Shader file not found: {shader_path.absolute()}")
                return ""

            with open(shader_path, "r") as f:
                content = f.read()
                log(f"Loaded shader: {path} ({len(content)} bytes)")
                return content
        except Exception as e:
            log(f"Failed to load shader {path}: {e}")
            return ""

    def _create_noise_texture(self):
        try:
            from PIL import Image

            texture_path = Path("background/texture/Psychedelic.png")
            if not texture_path.exists():
                log(f"Texture not found: {texture_path.absolute()}")
                return

            image = Image.open(texture_path).convert("RGB")
            img_data = image.tobytes()
            width, height = image.size

            self._noise_texture = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self._noise_texture)
            glTexImage2D(
                GL_TEXTURE_2D,
                0,
                GL_RGB,
                width,
                height,
                0,
                GL_RGB,
                GL_UNSIGNED_BYTE,
                img_data,
            )
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)

            log(f"Loaded texture: {width}x{height}")

        except Exception as e:
            log(f"Failed to load texture: {e}")
            import traceback

            log(traceback.format_exc())

    def paintGL(self):
        if not self._initialized or not self._main_program:
            glClearColor(0.1, 0.1, 0.15, 1.0)
            glClear(GL_COLOR_BUFFER_BIT)
            return

        try:
            w, h = self.width(), self.height()

            glViewport(0, 0, w, h)
            glClearColor(0.0, 0.0, 0.0, 1.0)
            glClear(GL_COLOR_BUFFER_BIT)

            glUseProgram(self._main_program)

            time_loc = glGetUniformLocation(self._main_program, "Time")
            viewport_loc = glGetUniformLocation(self._main_program, "ViewportSize")
            brightness_loc = glGetUniformLocation(self._main_program, "Brightness")

            if time_loc >= 0:
                glUniform1f(time_loc, self._time)

            if viewport_loc >= 0:
                glUniform2f(viewport_loc, float(w), float(h))

            if brightness_loc >= 0:
                glUniform1f(brightness_loc, self._brightness)

            if self._noise_texture:
                glActiveTexture(GL_TEXTURE0)
                glBindTexture(GL_TEXTURE_2D, self._noise_texture)
                tex_loc = glGetUniformLocation(self._main_program, "iChannel0")
                if tex_loc >= 0:
                    glUniform1i(tex_loc, 0)

            glBindVertexArray(self._vao)
            glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
            glBindVertexArray(0)

        except Exception as e:
            log(f"Render error: {e}")

    def resizeGL(self, w: int, h: int):
        glViewport(0, 0, w, h)

    def _update_time(self):
        self._time += 0.016
        self.update()
