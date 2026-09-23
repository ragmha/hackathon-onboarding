from __future__ import annotations

import os
import select
import sys
from types import TracebackType
from typing import TextIO

from .art import ANSI_DARK, ANSI_LIGHT, Frame, Role, rgb_for


ENTER = "\x1b[?1049h\x1b[?25l\x1b[?7l\x1b[0m\x1b[H\x1b[2J"
LEAVE = "\x1b[0m\x1b[?7h\x1b[?25h\x1b[?1049l"


class Painter:
    def __init__(self, mode: str = "truecolor", theme: str = "dark"):
        if mode not in ("truecolor", "ansi", "none"):
            raise ValueError(f"Unknown color mode: {mode}")
        self.mode = mode
        self.theme = theme
        self.previous: Frame | None = None
        self.styles: dict[tuple[int, int], str] = {}

    def style(self, role: int, level: int) -> str:
        key = (role, level)
        if key not in self.styles:
            if self.mode == "none":
                value = ""
            elif self.mode == "ansi":
                palette = ANSI_LIGHT if self.theme == "light" else ANSI_DARK
                value = f"\x1b[{palette[role]}m"
            else:
                r, g, b = rgb_for(role, level, self.theme)
                value = f"\x1b[38;2;{r};{g};{b}m"
            self.styles[key] = value
        return self.styles[key]

    def encode(self, frame: Frame) -> str:
        old = self.previous
        resized = old is None or (old.width, old.height) != (frame.width, frame.height)
        parts = ["\x1b[0m"]
        if self.mode == "truecolor":
            r, g, b = rgb_for(Role.BACKGROUND, 0, self.theme)
            parts.append(f"\x1b[48;2;{r};{g};{b}m")
        if resized:
            parts.append("\x1b[2J")
        changed = False
        for y in range(frame.height):
            start = y * frame.width
            row = frame.cells[start:start + frame.width]
            left, right = 0, frame.width
            if not resized and old is not None:
                old_row = old.cells[start:start + frame.width]
                while left < right and row[left] == old_row[left]:
                    left += 1
                while right > left and row[right - 1] == old_row[right - 1]:
                    right -= 1
            if left == right:
                continue
            changed = True
            parts.append(f"\x1b[{y + 1};{left + 1}H")
            current_style = None
            run: list[str] = []
            for char, role, level in row[left:right]:
                style = self.style(role, level)
                if current_style != style:
                    if run:
                        parts.append("".join(run))
                        run.clear()
                    parts.append(style)
                    current_style = style
                run.append(char)
            parts.append("".join(run))
        self.previous = frame
        return "".join(parts) if changed else ""


class Terminal:
    def __init__(self, output: TextIO | None = None):
        self.output = output if output is not None else sys.stdout
        self.input_mode = None
        self.windows_mode: tuple[object, int, int] | None = None
        self.entered = False

    def _enable_windows_ansi(self) -> None:
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetStdHandle.argtypes = [wintypes.DWORD]
        kernel.GetStdHandle.restype = wintypes.HANDLE
        kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.GetConsoleMode.restype = wintypes.BOOL
        kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.SetConsoleMode.restype = wintypes.BOOL
        handle = kernel.GetStdHandle(-11 & 0xFFFFFFFF)
        mode = wintypes.DWORD()
        if not kernel.GetConsoleMode(handle, ctypes.byref(mode)):
            raise OSError("Cannot access the Windows console. Use Windows Terminal or --static.")
        if not kernel.SetConsoleMode(handle, mode.value | 0x0004):
            raise OSError("This console does not support ANSI animation. Use --static.")
        self.windows_mode = (kernel, handle, mode.value)

    def __enter__(self) -> Terminal:
        try:
            if os.name == "nt":
                self._enable_windows_ansi()
            else:
                import termios
                import tty

                self.input_mode = termios.tcgetattr(sys.stdin.fileno())
                tty.setcbreak(sys.stdin.fileno())
            self.entered = True
            self.output.write(ENTER)
            self.output.flush()
        except BaseException:
            self.close()
            raise
        return self

    def close(self) -> None:
        try:
            if self.entered:
                self.entered = False
                self.output.write(LEAVE)
                self.output.flush()
        finally:
            if self.input_mode is not None:
                import termios

                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self.input_mode)
                self.input_mode = None
            if self.windows_mode is not None:
                kernel, handle, mode = self.windows_mode
                self.windows_mode = None
                if not kernel.SetConsoleMode(handle, mode):
                    raise OSError("Could not restore the original Windows console mode.")

    def __exit__(
        self, exc_type: type[BaseException] | None,
        exc: BaseException | None, traceback: TracebackType | None,
    ) -> None:
        self.close()

    def keys(self) -> list[str]:
        if os.name == "nt":
            import msvcrt

            result = []
            while msvcrt.kbhit():
                char = msvcrt.getwch()
                if char in ("\x00", "\xe0"):
                    if msvcrt.kbhit():
                        msvcrt.getwch()
                    continue
                result.append(char)
            return result
        if not select.select([sys.stdin], [], [], 0)[0]:
            return []
        data = os.read(sys.stdin.fileno(), 64).decode("utf-8", errors="replace")
        if data == "\x1b" and select.select([sys.stdin], [], [], 0.025)[0]:
            data += os.read(sys.stdin.fileno(), 64).decode("utf-8", errors="replace")
        for sequence in ("\x1b[A", "\x1b[B", "\x1b[C", "\x1b[D"):
            data = data.replace(sequence, "\t")
        return list(data)
