"""Characters, not a dashboard: one sculptural Copilot head owns the stage.

The MIT-licensed Primer Octicon supplies the silhouette. A custom relief,
character-density lighting, and restrained orbital motion give it depth.
The terminal's own font is the medium; the title is typeset text, not a logo
asset. Wide screens use a mascot/title duet; narrow screens stack the pair.
The animation is an independent study, not GitHub's original CLI animation.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from enum import IntEnum
from importlib.resources import files

from .lettering import (
    BLOCKS, DEFAULT_CAPTION, TITLE, WORDMARK, WORDMARK_HEIGHT, WORDMARK_WIDTH,
    COMPACT_WORDMARK, COMPACT_WORDMARK_WIDTH, ascii_glyph,
)


class Role(IntEnum):
    BACKGROUND = 0
    STAR = 1
    HEAD = 2
    GOGGLES = 3
    LENS = 4
    EYES = 5
    RIM = 6
    TITLE = 7
    CAPTION = 8
    MUTED = 9
    ORBIT = 10
    WORDMARK = 11
    SHADOW = 12


Cell = tuple[str, int, int]
EMPTY: Cell = (" ", Role.BACKGROUND, 0)
RAMP = " .,:;irsXA253hMHGS#9B&@"
SCENES = ("orbit", "warp", "signal")
MIN_WIDTH, MIN_HEIGHT = COMPACT_WORDMARK_WIDTH + 1, 22

DARK_COLORS = (
    (13, 17, 22), (113, 141, 181), (173, 150, 255),
    (100, 217, 255), (32, 104, 157), (201, 255, 216),
    (121, 116, 205), (239, 246, 255), (145, 229, 180),
    (169, 183, 203), (120, 101, 192),
    (57, 197, 207), (177, 186, 196),
)
LIGHT_COLORS = (
    (247, 249, 252), (96, 114, 143), (108, 61, 185),
    (13, 98, 151), (13, 55, 88), (16, 106, 66),
    (76, 68, 140), (27, 31, 36), (20, 108, 58),
    (76, 88, 108), (123, 98, 166),
    (30, 64, 175), (100, 116, 139),
)
ANSI_DARK = (39, 90, 95, 96, 34, 92, 35, 97, 92, 37, 35, 36, 37)
ANSI_LIGHT = (39, 90, 35, 34, 34, 32, 35, 30, 32, 90, 35, 34, 90)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def ease_out(value: float) -> float:
    return 1.0 - (1.0 - clamp(value)) ** 4


def rgb_for(role: int, level: int, theme: str = "dark") -> tuple[int, int, int]:
    colors = LIGHT_COLORS if theme == "light" else DARK_COLORS
    base = colors[role]
    if role == Role.BACKGROUND:
        return base
    if theme == "light":
        factor = 0.42 + 0.58 * level / 15
        background = colors[0]
        return tuple(round(bg + (c - bg) * factor) for c, bg in zip(base, background))
    factor = 0.24 + 0.76 * level / 15
    return tuple(round(c * factor) for c in base)


class Frame:
    def __init__(self, width: int, height: int):
        if width < 1 or height < 1:
            raise ValueError("Frame dimensions must be positive.")
        self.width = width
        self.height = height
        self.cells: list[Cell] = [EMPTY] * (width * height)
        self.depth = [-math.inf] * (width * height)

    def put(self, x: int, y: int, char: str, role: int, level: int = 15) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.cells[y * self.width + x] = (char, role, max(0, min(15, level)))

    def point(self, x: int, y: int, depth: float, char: str, role: int, level: int) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            index = y * self.width + x
            if depth > self.depth[index]:
                self.depth[index] = depth
                self.cells[index] = (char, role, max(0, min(15, level)))

    def text(self, x: int, y: int, value: str, role: int = Role.MUTED, level: int = 15) -> None:
        for offset, char in enumerate(value):
            self.put(x + offset, y, char, role, level)

    def centered(self, y: int, value: str, role: int = Role.MUTED, level: int = 15) -> None:
        self.text((self.width - len(value)) // 2, y, value, role, level)

    def plain(self) -> str:
        return "\n".join(
            "".join(cell[0] for cell in self.cells[y * self.width:(y + 1) * self.width]).rstrip()
            for y in range(self.height)
        )


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    z: float
    nx: float
    ny: float
    nz: float
    role: int
    source_y: float


def load_mesh() -> tuple[Point, ...]:
    document = json.loads(
        files("copilot_showcase").joinpath("assets", "copilot.json").read_text(encoding="utf-8")
    )
    rows = document["rows"]
    width = document["width"]
    height = document["height"]
    if (
        not isinstance(width, int) or not isinstance(height, int)
        or not 8 <= width <= 256 or not 8 <= height <= 256
        or len(rows) != height or any(len(row) != width for row in rows)
        or any(char not in ".23456" for row in rows for char in row)
    ):
        raise ValueError("The bundled mascot artwork has invalid dimensions or materials.")
    points = []
    for sy, row in enumerate(rows):
        for sx, value in enumerate(row):
            if value == ".":
                continue
            x = (sx + 0.5) / width * 2 - 1
            y = 1 - (sy + 0.5) / height * 2
            curved = math.sqrt(max(0.02, 1 - (x / 1.18) ** 2 - (y / 1.42) ** 2))
            z = 0.34 * curved
            role = int(value)
            front_z = z + (0.14 if role in (Role.GOGGLES, Role.LENS) else 0)
            for side in (1, -1):
                nx, ny, nz = x * 0.50, y * 0.27, side * curved
                length = math.sqrt(nx * nx + ny * ny + nz * nz)
                points.append(Point(
                    x, y, front_z if side == 1 else -z,
                    nx / length, ny / length, nz / length,
                    role if side == 1 else Role.RIM, sy / height,
                ))
    return tuple(points)


class SceneRenderer:
    def __init__(self, seed: int = 42):
        self.mesh = load_mesh()
        rng = random.Random(seed)
        self.stars = tuple(
            (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.random(), rng.random())
            for _ in range(95)
        )

    @staticmethod
    def layout(
        width: int, height: int, ascii_only: bool = False,
    ) -> tuple[float, float, float, int, int, int]:
        word_height = WORDMARK_HEIGHT
        word_width = COMPACT_WORDMARK_WIDTH if width < WORDMARK_WIDTH + 1 else WORDMARK_WIDTH
        if width >= 112 and height >= 24:
            scale = min((height - 9) / 1.85, 18, (width * 0.44 - 5) / 4.2)
            cx, cy = width * 0.26, height * 0.46
            title_x, title_y = round(width * 0.73 - word_width / 2), round(cy - word_height / 2)
        else:
            title_y = height - word_height - 5
            padding = 4 if height < 28 else 6
            scale = min((title_y - padding) / 1.85, 17, (width - 12) / 4.2)
            cx, cy = width / 2, (title_y - 3) / 2
            title_x = (width - word_width) // 2
        return cx, cy, max(1.0, scale), title_x, title_y, word_height

    def background(self, frame: Frame, elapsed: float, scene: str) -> None:
        w, h = frame.width, frame.height
        count = min(len(self.stars), max(12, w * h // 70))
        for index, (sx, sy, distance, phase) in enumerate(self.stars[:count]):
            if scene == "warp":
                depth = 0.12 + ((distance - elapsed * 0.11) % 1.0) * 1.8
                x = w / 2 + sx * w * 0.31 / depth
                y = h / 2 + sy * h * 0.35 / depth
                level = round(5 + 8 * clamp(1 - depth / 2))
                char = "+" if depth < 0.28 else "."
                if depth < 0.48:
                    tail_x = round(x - math.copysign(1, sx))
                    tail_y = round(y - math.copysign(0.5, sy))
                    frame.put(tail_x, tail_y, ".", Role.STAR, 3)
            else:
                drift = elapsed * (0.0008 + distance * 0.0015)
                x = ((sx / 2 + 0.5 + drift) % 1) * w
                y = (sy / 2 + 0.5) * max(1, h - 3)
                level = round(3 + 5 * (0.5 + 0.5 * math.sin(elapsed * 0.65 + phase * 8)))
                char = "+" if index % 19 == 0 else "."
            frame.put(round(x), round(y), char, Role.STAR, level)

    @staticmethod
    def wordmark(frame: Frame, x: int, y: int, elapsed: float, ascii_only: bool) -> None:
        wordmark = COMPACT_WORDMARK if frame.width < WORDMARK_WIDTH + 1 else WORDMARK
        reveal = round(len(wordmark[0]) * ease_out((elapsed - 0.35) / 1.7))
        for row, value in enumerate(wordmark):
            for column, char in enumerate(value[:reveal]):
                if char != " ":
                    frame.put(
                        x + column, y + row, ascii_glyph(char) if ascii_only else char,
                        Role.WORDMARK if char in BLOCKS else Role.SHADOW,
                    )

    def render(
        self, width: int, height: int, elapsed: float,
        scene: str = "orbit", event: str = DEFAULT_CAPTION,
        ascii_only: bool = False, show_help: bool = False, paused: bool = False,
        color_mode: str = "truecolor", speed: float = 1.0,
    ) -> Frame:
        if scene not in SCENES:
            raise ValueError(f"Unknown scene: {scene}")
        frame = Frame(width, height)
        if width < MIN_WIDTH or height < MIN_HEIGHT:
            frame.centered(max(0, height // 2 - 2), TITLE, Role.TITLE)
            frame.centered(max(1, height // 2), event[:width], Role.CAPTION)
            if height >= 8:
                frame.centered(height - 3, f"Enlarge to {MIN_WIDTH} x {MIN_HEIGHT} for the artwork."[:width])
                frame.centered(height - 1, "Q quit | Space pause"[:width])
            return frame

        self.background(frame, elapsed, scene)
        cx, cy, scale, title_x, title_y, word_height = self.layout(width, height, ascii_only)
        word_width = COMPACT_WORDMARK_WIDTH if width < WORDMARK_WIDTH + 1 else WORDMARK_WIDTH
        entrance = ease_out(elapsed / 2.0)
        cx -= (1 - entrance) * min(width * 0.35, 40)
        cy += math.sin(elapsed * 0.72) * 0.60
        scale *= 0.32 + 0.68 * entrance
        yaw = (1 - entrance) * 1.12 + math.sin(elapsed * 0.37) * 0.55
        pitch = math.sin(elapsed * 0.29) * 0.12
        roll = math.sin(elapsed * 0.41) * 0.045
        if scene == "warp":
            yaw += math.sin(elapsed * 0.7) * 0.18
            roll += math.sin(elapsed * 0.55) * 0.045
        ca, sa = math.cos(yaw), math.sin(yaw)
        cb, sb = math.cos(pitch), math.sin(pitch)
        cc, sc = math.cos(roll), math.sin(roll)

        # The same transform is used for surface positions and lighting normals.
        matrix = (
            cc * ca - sc * sb * sa, -sc * cb, cc * sa + sc * sb * ca,
            sc * ca + cc * sb * sa, cc * cb, sc * sa - cc * sb * ca,
            -cb * sa, sb, cb * ca,
        )
        a, b, c, d, e, f, g, j, k = matrix
        if scene != "warp":
            for index in range(145):
                angle = index * math.tau / 145 + elapsed * 0.14
                x = 1.38 * math.cos(angle)
                y = 0.39 * math.sin(angle) + 0.24 * x
                z = 0.80 * math.sin(angle)
                perspective = 4 / (4.6 - z)
                px = round(cx + x * scale * 2.0 * perspective)
                py = round(cy - y * scale * perspective)
                char = "*" if index in (0, 72) else "."
                frame.point(px, py, z, char, Role.ORBIT, 12 if char == "*" else 3)

        scan_y = (elapsed * 0.16) % 1
        for point in self.mesh:
            nx = a * point.nx + b * point.ny + c * point.nz
            ny = d * point.nx + e * point.ny + f * point.nz
            nz = g * point.nx + j * point.ny + k * point.nz
            if nz < -0.04:
                continue
            x = a * point.x + b * point.y + c * point.z
            y = d * point.x + e * point.y + f * point.z
            z = g * point.x + j * point.y + k * point.z
            perspective = 4 / (4.6 - z)
            px = round(cx + x * scale * 2.0 * perspective)
            py = round(cy - y * scale * perspective)
            diffuse = max(0, -0.42 * nx + 0.55 * ny + 0.72 * nz)
            specular = max(0, -0.22 * nx + 0.33 * ny + 0.92 * nz) ** 22
            light = clamp(0.28 + diffuse * 0.60 + specular * 0.28)
            role = point.role
            if role == Role.LENS:
                light = clamp(0.08 + diffuse * 0.15 + specular * 0.65)
            elif role == Role.GOGGLES:
                light = clamp(light + 0.12)
            elif role == Role.EYES:
                light = 0.96
            if scene == "signal":
                light = clamp(light + 0.28 * math.exp(-((point.source_y - scan_y) / 0.055) ** 2))
            level = round(light * 15)
            char = RAMP[max(1, round(light * (len(RAMP) - 1)))]
            frame.point(px, py, z, char, role, level)

        # Blank only the title's small rectangle; never clear the whole screen per frame.
        for y in range(title_y - 2, min(height - 2, title_y + word_height + 3)):
            for x in range(max(0, title_x - 2), min(width, title_x + word_width + 2)):
                frame.put(x, y, " ", Role.BACKGROUND, 0)
        frame.text(title_x, title_y - 2, "Welcome to", Role.TITLE)
        self.wordmark(frame, title_x, title_y, elapsed, ascii_only)
        caption = event[:max(0, min(width - 4, 50))]
        frame.text(title_x + (word_width - len(caption)) // 2, title_y + word_height + 2, caption, Role.CAPTION)
        if show_help or paused:
            help_line = "Space pause  1-3 scene  C color  +/- speed  R replay  H help  Q quit"
            short_help = "Space pause | Tab scene | H help | Q quit"
            if len(short_help) > width - 2:
                short_help = "Space pause | H help | Q quit"
            status = f"{'PAUSED' if paused else scene.upper()}  /  {color_mode}  /  {speed:.2g}x"
            frame.centered(height - 2, status[:width - 2], Role.MUTED)
            frame.centered(height - 1, help_line if width > len(help_line) + 2 else short_help[:width - 2])
        elif elapsed < 7:
            frame.centered(height - 1, "H controls   Space pause   Q quit", Role.MUTED, 13)
        return frame
