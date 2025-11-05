from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtGui import QSurfaceFormat
from OpenGL.GL import *
from OpenGL.GL.shaders import compileShader, compileProgram

from src.common.vars import log


class OpenGLBackground(QOpenGLWidget):
    def __init__(self):
        super().__init__()

        self._program = None
        self._vao = None
        self._vbo = None
        self._time_loc = None
        self._viewport_loc = None
        self._texture = None
        self._time = 0.0

        self._timer = QTimer()
        self._timer.timeout.connect(self._update_time)
        self._timer.start(16)

        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        self.setFormat(fmt)

    def initializeGL(self):
        try:
            vertex_shader = self._load_shader("background/vertex.glsl")
            fragment_shader = self._load_shader("background/fragment.glsl")

            self._program = compileProgram(
                compileShader(vertex_shader, GL_VERTEX_SHADER),
                compileShader(fragment_shader, GL_FRAGMENT_SHADER),
            )

            self._time_loc = glGetUniformLocation(self._program, "Time")
            self._viewport_loc = glGetUniformLocation(self._program, "ViewportSize")

            vertices = [
                -1.0,
                -1.0,
                0.0,
                1.0,
                -1.0,
                0.0,
                -1.0,
                1.0,
                0.0,
                1.0,
                1.0,
                0.0,
            ]

            self._vao = glGenVertexArrays(1)
            glBindVertexArray(self._vao)

            self._vbo = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
            glBufferData(
                GL_ARRAY_BUFFER,
                len(vertices) * 4,
                (GLfloat * len(vertices))(*vertices),
                GL_STATIC_DRAW,
            )

            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, None)
            glEnableVertexAttribArray(0)

            glBindVertexArray(0)

            self._create_noise_texture()

            log("opengl background initialized")

        except Exception as e:
            log(f"failed to initialize opengl: {e}")

    def _load_shader(self, path: str) -> str:
        try:
            with open(path, "r") as f:
                return f.read()
        except Exception as e:
            log(f"failed to load shader {path}: {e}")
            return ""

    def _create_noise_texture(self):
        try:
            from PIL import Image

            texture_path = Path("background/texture/Psychedelic.png")

            if not texture_path.exists():
                log(f"texture file not found: {texture_path}")
                return

            image = Image.open(texture_path)
            image = image.convert("RGB")

            img_data = image.tobytes()
            width, height = image.size

            self._texture = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self._texture)
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

            log(f"loaded texture: {texture_path} ({width}x{height})")

        except Exception as e:
            log(f"failed to load texture: {e}")

    def paintGL(self):
        try:
            glClearColor(0.15, 0.15, 0.13, 1.0)
            glClear(GL_COLOR_BUFFER_BIT)

            if not self._program:
                return

            glUseProgram(self._program)

            if self._time_loc >= 0:
                glUniform1f(self._time_loc, self._time)

            if self._viewport_loc >= 0:
                glUniform2f(
                    self._viewport_loc, float(self.width()), float(self.height())
                )

            if self._texture:
                glActiveTexture(GL_TEXTURE0)
                glBindTexture(GL_TEXTURE_2D, self._texture)
                glUniform1i(glGetUniformLocation(self._program, "iChannel0"), 0)

            glBindVertexArray(self._vao)
            glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
            glBindVertexArray(0)

        except Exception as e:
            log(f"opengl render error: {e}")

    def resizeGL(self, w: int, h: int):
        glViewport(0, 0, w, h)

    def _update_time(self):
        self._time += 0.016
        self.update()
