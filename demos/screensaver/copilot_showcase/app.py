from __future__ import annotations

import argparse
import math
import os
import shutil
import signal
import sys
import time
from dataclasses import dataclass

from .art import SCENES, SceneRenderer
from .lettering import ALLOWED_GLYPHS, DEFAULT_CAPTION, TITLE
from .terminal import Painter, Terminal


@dataclass
class Playback:
    elapsed: float = 0.0
    paused: bool = False
    show_help: bool = False
    scene: str = "tour"
    speed: float = 1.0
    color: str = "truecolor"
    running: bool = True

    @property
    def active_scene(self) -> str:
        return SCENES[int(self.elapsed // 24) % len(SCENES)] if self.scene == "tour" else self.scene

    def advance(self, seconds: float) -> None:
        if not self.paused:
            self.elapsed += max(0, seconds) * self.speed

    def key(self, key: str) -> None:
        key = key.lower()
        if key in ("q", "\x1b", "\x03"):
            self.running = False
        elif key == " ":
            self.paused = not self.paused
        elif key == "h":
            self.show_help = not self.show_help
        elif key in ("1", "2", "3"):
            self.scene = SCENES[int(key) - 1]
        elif key == "\t":
            self.scene = SCENES[(SCENES.index(self.active_scene) + 1) % len(SCENES)]
        elif key == "a":
            self.scene = "tour"
        elif key == "r":
            self.elapsed = 0.0
        elif key in ("+", "="):
            self.speed = min(2.0, self.speed + 0.25)
        elif key == "-":
            self.speed = max(0.25, self.speed - 0.25)
        elif key == "c":
            modes = ("truecolor", "ansi", "none")
            self.color = modes[(modes.index(self.color) + 1) % len(modes)]


def finite_float(value: str) -> float:
    try:
        result = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Enter a finite number.") from error
    if not math.isfinite(result):
        raise argparse.ArgumentTypeError("Enter a finite number.")
    return result


def event_name(value: str) -> str:
    if not value.strip() or len(value) > 48 or any(ord(char) < 32 or ord(char) > 126 for char in value):
        raise argparse.ArgumentTypeError("Use 1-48 printable ASCII characters for the event name.")
    return value


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="An offline HACKATHON terminal screensaver with a shaded Octicon mascot.",
        epilog="Keys: Space pause; 1/2/3 or Tab scene; A auto-tour; C color; +/- speed; R replay; H help; Q/Esc quit.",
    )
    result.add_argument("--event", type=event_name, default=DEFAULT_CAPTION, help="Event caption (up to 48 ASCII characters).")
    result.add_argument("--art", choices=("sculpture",), default="sculpture",
                        help="The bundled MIT-licensed Octicon sculpture (default and only artwork).")
    result.add_argument("--scene", choices=("tour",) + SCENES, default="orbit")
    result.add_argument("--fps", type=int, default=24, help="Frame-rate ceiling, 5-60 (default: 24).")
    result.add_argument("--speed", type=finite_float, default=1.0, help="Motion speed, 0.25-2.0.")
    result.add_argument("--duration", type=finite_float, help="Exit after this many seconds; omit to loop.")
    result.add_argument("--color", choices=("auto", "truecolor", "ansi", "none"), default="auto")
    result.add_argument("--theme", choices=("dark", "light"), default="dark")
    result.add_argument("--ascii", action="store_true", help="Only use printable ASCII, including the title.")
    result.add_argument("--static", action="store_true", help="Print one still frame, without terminal control sequences.")
    result.add_argument("--screen-reader", action="store_true", help="Print a plain-language description and exit.")
    result.add_argument("--seed", type=int, default=42, help="Reproducible starfield seed.")
    return result


def color_mode(requested: str) -> str:
    if requested != "auto":
        return requested
    if "NO_COLOR" in os.environ:
        return "none"
    if (
        os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit")
        or os.environ.get("WT_SESSION") or os.name == "nt"
    ):
        return "truecolor"
    return "ansi"


def dimensions() -> tuple[int, int]:
    size = shutil.get_terminal_size(fallback=(100, 38))
    # Leave the last column/row untouched to avoid wrap and scroll at the bottom-right.
    return max(1, min(size.columns - 1, 220)), max(1, min(size.lines - 1, 75))


def animate(args: argparse.Namespace, renderer: SceneRenderer, ascii_only: bool) -> int:
    state = Playback(scene=args.scene, speed=args.speed, color=color_mode(args.color))
    previous_handler = signal.getsignal(signal.SIGTERM)

    def stop(signum: int, frame: object) -> None:
        state.running = False

    signal.signal(signal.SIGTERM, stop)
    painter = Painter(state.color, args.theme)
    started = previous = time.monotonic()
    old_dimensions = None
    old_state = None
    try:
        with Terminal() as terminal:
            while state.running:
                frame_started = time.monotonic()
                if args.duration is not None and frame_started - started >= args.duration:
                    break
                state.advance(min(frame_started - previous, 0.25))
                previous = frame_started
                for key in terminal.keys():
                    state.key(key)
                if not state.running:
                    break
                size = dimensions()
                fingerprint = (
                    state.elapsed, state.paused, state.show_help,
                    state.active_scene, state.color, state.speed,
                )
                if fingerprint != old_state or size != old_dimensions:
                    if painter.mode != state.color:
                        painter = Painter(state.color, args.theme)
                    frame = renderer.render(
                        *size, state.elapsed, state.active_scene, args.event,
                        ascii_only, state.show_help, state.paused, state.color, state.speed,
                    )
                    output = painter.encode(frame)
                    if output:
                        terminal.output.write(output)
                        terminal.output.flush()
                    old_state, old_dimensions = fingerprint, size
                delay = max(0, (0.1 if state.paused else 1 / args.fps) - (time.monotonic() - frame_started))
                time.sleep(delay)
    except KeyboardInterrupt:
        return 0
    finally:
        signal.signal(signal.SIGTERM, previous_handler)
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = parser()
    args = arguments.parse_args(argv)
    if not 5 <= args.fps <= 60:
        arguments.error("--fps must be between 5 and 60.")
    if not 0.25 <= args.speed <= 2:
        arguments.error("--speed must be between 0.25 and 2.")
    if args.duration is not None and args.duration <= 0:
        arguments.error("--duration must be greater than zero.")
    if args.screen_reader:
        print(f"{TITLE} ASCII showcase. Event caption: {args.event}.")
        print("A shaded mascot with goggles and two eyes, based on the MIT-licensed GitHub Copilot Octicon.")
        print("Large HACKATHON lettering has an outline shadow.")
        print("Motion and decorative output are disabled.")
        return 0
    ascii_only = args.ascii
    if not ascii_only:
        try:
            "".join(ALLOWED_GLYPHS).encode(sys.stdout.encoding or "ascii")
        except (UnicodeEncodeError, LookupError):
            ascii_only = True
    try:
        renderer = SceneRenderer(args.seed)
        interactive = sys.stdout.isatty() and sys.stdin.isatty() and os.environ.get("TERM") != "dumb"
        if args.static or not interactive:
            width, height = dimensions()
            if not interactive:
                width, height = 100, 38
            print(renderer.render(
                width, height, 6.0,
                "orbit" if args.scene == "tour" else args.scene,
                args.event, True,
            ).plain())
            return 0
        return animate(args, renderer, ascii_only)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Cannot run the screensaver: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
