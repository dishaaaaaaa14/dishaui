"""Minimal OpenGL 3.3 renderer for chalk meshes and the board background."""

from __future__ import annotations

import ctypes

import numpy as np
from OpenGL import GL

import config

from .mesh import Mesh

CHALK_VERTEX = """
#version 330 core
layout(location = 0) in vec2 a_pos;
layout(location = 1) in vec4 a_color;
out vec4 v_color;
void main() {
    gl_Position = vec4(a_pos, 0.0, 1.0);
    v_color = a_color;
}
"""

CHALK_FRAGMENT = """
#version 330 core
in vec4 v_color;
out vec4 frag_color;
float hash(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}
void main() {
    float grain = hash(gl_FragCoord.xy);
    float alpha = v_color.a * (0.84 + 0.16 * grain);
    frag_color = vec4(v_color.rgb, alpha);
}
"""

BACKGROUND_VERTEX = """
#version 330 core
layout(location = 0) in vec2 a_pos;
out vec2 v_uv;
void main() {
    gl_Position = vec4(a_pos, 0.0, 1.0);
    v_uv = a_pos * 0.5 + 0.5;
}
"""

BACKGROUND_FRAGMENT = """
#version 330 core
in vec2 v_uv;
uniform vec3 u_bg;
uniform vec2 u_resolution;
uniform float u_time;
out vec4 frag_color;
float hash(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}
void main() {
    float d = length(v_uv - vec2(0.5, 0.48));
    float vignette = smoothstep(0.78, 0.18, d) * 0.018;
    float dust = hash(floor(v_uv * u_resolution * 0.5) + u_time * 0.02);
    float grain = (dust - 0.5) * 0.022;
    vec3 color = u_bg + vec3(vignette + grain);
    frag_color = vec4(color, 1.0);
}
"""


def _compile(source: str, kind: int) -> int:
    shader = GL.glCreateShader(kind)
    GL.glShaderSource(shader, source)
    GL.glCompileShader(shader)
    if not GL.glGetShaderiv(shader, GL.GL_COMPILE_STATUS):
        log = GL.glGetShaderInfoLog(shader)
        detail = log.decode("utf-8", errors="replace") if isinstance(log, bytes) else str(log)
        raise RuntimeError(detail)
    return shader


class Program:
    def __init__(self, vertex_source: str, fragment_source: str) -> None:
        vertex = _compile(vertex_source, GL.GL_VERTEX_SHADER)
        fragment = _compile(fragment_source, GL.GL_FRAGMENT_SHADER)
        self.handle = GL.glCreateProgram()
        GL.glAttachShader(self.handle, vertex)
        GL.glAttachShader(self.handle, fragment)
        GL.glLinkProgram(self.handle)
        GL.glDeleteShader(vertex)
        GL.glDeleteShader(fragment)
        if not GL.glGetProgramiv(self.handle, GL.GL_LINK_STATUS):
            log = GL.glGetProgramInfoLog(self.handle)
            detail = log.decode("utf-8", errors="replace") if isinstance(log, bytes) else str(log)
            raise RuntimeError(detail)
    def use(self) -> None:
        GL.glUseProgram(self.handle)

    def uniform(self, name: str) -> int:
        return GL.glGetUniformLocation(self.handle, name)

    def delete(self) -> None:
        GL.glDeleteProgram(self.handle)


class GLRenderer:
    def __init__(self) -> None:
        self.chalk_program: Program | None = None
        self.background_program: Program | None = None
        self.chalk_vao = 0
        self.chalk_vbo = 0
        self.background_vao = 0
        self.background_vbo = 0
        self.width = 0
        self.height = 0

    def initialize(self) -> None:
        self.chalk_program = Program(CHALK_VERTEX, CHALK_FRAGMENT)
        self.background_program = Program(BACKGROUND_VERTEX, BACKGROUND_FRAGMENT)
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)

        self.chalk_vao = GL.glGenVertexArrays(1)
        self.chalk_vbo = GL.glGenBuffers(1)
        GL.glBindVertexArray(self.chalk_vao)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.chalk_vbo)
        stride = 6 * 4
        GL.glEnableVertexAttribArray(0)
        GL.glVertexAttribPointer(0, 2, GL.GL_FLOAT, GL.GL_FALSE, stride, ctypes.c_void_p(0))
        GL.glEnableVertexAttribArray(1)
        GL.glVertexAttribPointer(1, 4, GL.GL_FLOAT, GL.GL_FALSE, stride, ctypes.c_void_p(8))

        quad = np.array(
            [-1.0, -1.0, 1.0, -1.0, 1.0, 1.0, -1.0, -1.0, 1.0, 1.0, -1.0, 1.0],
            dtype=np.float32,
        )
        self.background_vao = GL.glGenVertexArrays(1)
        self.background_vbo = GL.glGenBuffers(1)
        GL.glBindVertexArray(self.background_vao)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.background_vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, quad.nbytes, quad, GL.GL_STATIC_DRAW)
        GL.glEnableVertexAttribArray(0)
        GL.glVertexAttribPointer(0, 2, GL.GL_FLOAT, GL.GL_FALSE, 2 * 4, ctypes.c_void_p(0))
        GL.glBindVertexArray(0)

    def resize(self, width: int, height: int) -> None:
        self.width = max(1, width)
        self.height = max(1, height)
        GL.glViewport(0, 0, self.width, self.height)

    def draw_background(self, time_s: float = 0.0) -> None:
        GL.glClearColor(*config.BOARD_BG, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        if self.background_program is None:
            return
        self.background_program.use()
        GL.glUniform3f(
            self.background_program.uniform("u_bg"),
            *config.BOARD_BG,
        )
        GL.glUniform2f(
            self.background_program.uniform("u_resolution"),
            float(self.width),
            float(self.height),
        )
        GL.glUniform1f(self.background_program.uniform("u_time"), time_s)
        GL.glBindVertexArray(self.background_vao)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 6)
        GL.glBindVertexArray(0)

    def draw_mesh(self, mesh: Mesh, alpha_scale: float = 1.0) -> None:
        if not mesh or self.chalk_program is None:
            return
        vertices = np.fromiter(mesh.vertices, dtype=np.float32)
        self.chalk_program.use()
        GL.glBindVertexArray(self.chalk_vao)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.chalk_vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL.GL_DYNAMIC_DRAW)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, mesh.vertex_count)
        GL.glBindVertexArray(0)

    def dispose(self) -> None:
        for program in (self.chalk_program, self.background_program):
            if program is not None:
                program.delete()
        if self.chalk_vbo:
            GL.glDeleteBuffers(1, [self.chalk_vbo])
        if self.background_vbo:
            GL.glDeleteBuffers(1, [self.background_vbo])
        if self.chalk_vao:
            GL.glDeleteVertexArrays(1, [self.chalk_vao])
        if self.background_vao:
            GL.glDeleteVertexArrays(1, [self.background_vao])
