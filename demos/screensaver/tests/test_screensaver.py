import argparse
import contextlib
import io
import itertools
import json
import os
import re
import runpy
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
import zipfile
from importlib.resources import files
from pathlib import Path
from unittest.mock import Mock, call, patch

from copilot_showcase.app import (
    Playback, animate, color_mode, event_name, finite_float, main, parser,
)
from copilot_showcase.art import Frame, Role, SCENES, SceneRenderer, load_mesh, rgb_for
from copilot_showcase.lettering import (
    BLOCKS, COMPACT_FONT, COMPACT_WORDMARK, COMPACT_WORDMARK_WIDTH,
    DEFAULT_CAPTION, FONT, TITLE, WORDMARK, WORDMARK_HEIGHT, WORDMARK_WIDTH,
    ascii_glyph, outlined_wordmark,
)
from copilot_showcase.terminal import ENTER, LEAVE, Painter, Terminal


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_FILES = {
    Path("copilot_showcase", name)
    for name in ("__init__.py", "__main__.py", "app.py", "art.py", "lettering.py", "terminal.py")
} | {
    Path("copilot_showcase", "assets", name)
    for name in ("copilot.json", "copilot.svg", "LICENSE-Octicons.txt")
}


class TTYBuffer(io.StringIO):
    def isatty(self):
        return True


class ArtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.renderer = SceneRenderer()

    def test_licensed_art_is_bundled_with_all_materials_and_provenance(self):
        mesh = load_mesh()
        self.assertGreater(len(mesh), 6000)
        self.assertEqual({point.role for point in mesh}, {2, 3, 4, 5, 6})
        assets = files("copilot_showcase").joinpath("assets")
        document = json.loads(assets.joinpath("copilot.json").read_text(encoding="utf-8"))
        self.assertEqual((document["width"], document["height"]), (96, 96))
        self.assertEqual(
            document["source"],
            "https://github.com/primer/octicons/blob/v19.15.3/icons/copilot-96.svg",
        )
        license_text = assets.joinpath("LICENSE-Octicons.txt").read_text(encoding="utf-8")
        self.assertIn("MIT License", license_text)
        self.assertIn("Copyright (c) 2025 GitHub Inc.", license_text)

    def test_all_scenes_resize_and_stay_inside_frame(self):
        sizes = (
            (1, 1), (35, 12), (38, 22), (41, 28), (46, 22), (47, 28),
            (48, 22), (72, 42), (112, 24), (180, 55), (220, 75),
        )
        for scene, (width, height) in itertools.product(SCENES, sizes):
            with self.subTest(scene=scene, size=(width, height)):
                frame = self.renderer.render(width, height, 6, scene, ascii_only=True)
                self.assertEqual(len(frame.cells), width * height)
                self.assertTrue(all(32 <= ord(char) <= 126 for char, _, _ in frame.cells))
                self.assertTrue(all(0 <= level <= 15 for _, _, level in frame.cells))
                if width >= 38 and height >= 22:
                    self.assertIn("Welcome to", frame.plain())
                    self.assertIn(DEFAULT_CAPTION, frame.plain())
                    self.assertGreater(sum(role == Role.EYES for _, role, _ in frame.cells), 0)

    def test_animation_keeps_moving_after_the_entrance(self):
        first = self.renderer.render(120, 40, 4)
        second = self.renderer.render(120, 40, 7)
        self.assertGreater(sum(a != b for a, b in zip(first.cells, second.cells)), 100)

    def test_seed_is_reproducible(self):
        self.assertEqual(
            self.renderer.render(80, 35, 5).cells,
            SceneRenderer().render(80, 35, 5).cells,
        )
        self.assertNotEqual(self.renderer.stars, SceneRenderer(seed=7).stars)

    def test_invalid_scene_and_dimensions_fail_explicitly(self):
        with self.assertRaises(ValueError):
            self.renderer.render(80, 35, 1, "unknown")
        with self.assertRaises(ValueError):
            Frame(0, 12)

    def test_invalid_material_map_fails_explicitly(self):
        for document in (
            {"width": 7, "height": 8, "rows": ["." * 7] * 8},
            {"width": 257, "height": 8, "rows": ["." * 257] * 8},
            {"width": 8, "height": 8, "rows": ["." * 8]},
            {"width": 8, "height": 8, "rows": ["X" * 8] * 8},
        ):
            with self.subTest(document=document):
                with patch("copilot_showcase.art.json.loads", return_value=document):
                    with self.assertRaisesRegex(ValueError, "invalid dimensions or materials"):
                        load_mesh()

    def test_depth_test_and_brightness_bounds(self):
        frame = Frame(1, 1)
        frame.point(0, 0, 2, "@", Role.HEAD, 20)
        frame.point(0, 0, 1, ".", Role.STAR, 2)
        self.assertEqual(frame.cells[0], ("@", Role.HEAD, 15))
        frame.point(0, 0, 3, "#", Role.RIM, -1)
        self.assertEqual(frame.cells[0], ("#", Role.RIM, 0))

    def test_all_shipped_roles_have_dark_and_light_palettes(self):
        for role, theme, level in itertools.product(Role, ("dark", "light"), (0, 15)):
            self.assertTrue(all(0 <= value <= 255 for value in rgb_for(role, level, theme)))
            for mode in ("truecolor", "ansi", "none"):
                Painter(mode, theme).style(role, level)
        self.assertEqual(rgb_for(Role.WORDMARK, 15), (57, 197, 207))
        self.assertEqual(rgb_for(Role.SHADOW, 15), (177, 186, 196))


class LetteringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.renderer = SceneRenderer()

    def test_both_widths_encode_every_pixel_of_all_nine_letters(self):
        self.assertEqual(TITLE, "HACKATHON")
        self.assertEqual((WORDMARK_WIDTH, WORDMARK_HEIGHT), (46, 6))
        self.assertEqual(COMPACT_WORDMARK_WIDTH, 37)
        for font, wordmark, pitch in ((FONT, WORDMARK, 5), (COMPACT_FONT, COMPACT_WORDMARK, 4)):
            for letter_index, letter in enumerate(TITLE):
                for y, row in enumerate(font[letter]):
                    for x, pixel in enumerate(row):
                        char = wordmark[y // 2][letter_index * pitch + x // 2]
                        mask = BLOCKS.index(char) if char in BLOCKS else 0
                        filled = bool(mask & (1 << ((y % 2) * 2 + x % 2)))
                        self.assertEqual(filled, pixel == "1", (pitch, letter_index, letter, x, y))
            self.assertLessEqual(
                {char for row in wordmark for char in row if char in BLOCKS},
                {" ", "\u2588", "\u258c", "\u2590"},
            )
        for invalid in ("", "COPILOT", "hackathon"):
            with self.assertRaises(ValueError):
                outlined_wordmark(invalid)

    def test_complete_title_and_shadow_survive_all_layouts(self):
        sizes = ((38, 22), (46, 28), (47, 22), (72, 42), (112, 24), (220, 75))
        for scene, (width, height), ascii_only in itertools.product(SCENES, sizes, (False, True)):
            with self.subTest(scene=scene, size=(width, height), ascii_only=ascii_only):
                frame = self.renderer.render(width, height, 6, scene, ascii_only=ascii_only)
                _, _, _, x, y, _ = self.renderer.layout(width, height)
                wordmark = COMPACT_WORDMARK if width < 47 else WORDMARK
                for dy, row in enumerate(wordmark):
                    for dx, char in enumerate(row):
                        self.assertTrue(0 <= x + dx < width)
                        self.assertTrue(0 <= y + dy < height - 2)
                        cell = frame.cells[(y + dy) * width + x + dx]
                        self.assertEqual(cell[0], ascii_glyph(char) if ascii_only else char)
                        if char != " ":
                            self.assertEqual(cell[1], Role.WORDMARK if char in BLOCKS else Role.SHADOW)

    def test_generic_labels_and_custom_caption(self):
        for size in ((35, 12), (52, 28), (120, 40)):
            text = self.renderer.render(*size, 6, event="BUILD TOGETHER", show_help=True).plain()
            self.assertIn("BUILD TOGETHER", text)
            self.assertNotIn("GitHub", text)
            self.assertNotIn("Copilot", text)


class PlaybackTests(unittest.TestCase):
    def test_pause_freezes_animation_and_tour(self):
        state = Playback(elapsed=23.9)
        state.key(" ")
        state.advance(8)
        self.assertEqual(state.elapsed, 23.9)
        self.assertEqual(state.active_scene, "orbit")
        state.key(" ")
        state.advance(1)
        self.assertEqual(state.active_scene, "warp")

    def test_clock_scales_with_speed_and_rejects_negative_steps(self):
        state = Playback(speed=0.5)
        state.advance(96)
        self.assertEqual(state.elapsed, 48)
        self.assertEqual(state.active_scene, "signal")
        state.advance(-20)
        self.assertEqual(state.elapsed, 48)
        state.advance(48)
        self.assertEqual(state.active_scene, "orbit")

    def test_all_documented_keys(self):
        state = Playback(elapsed=10)
        for key, scene in (("1", "orbit"), ("2", "warp"), ("3", "signal"), ("\t", "orbit")):
            state.key(key)
            self.assertEqual(state.active_scene, scene)
        state.key("a")
        self.assertEqual(state.scene, "tour")
        state.key("h")
        self.assertTrue(state.show_help)
        for expected in ("ansi", "none", "truecolor"):
            state.key("c")
            self.assertEqual(state.color, expected)
        for _ in range(30):
            state.key("+")
        self.assertEqual(state.speed, 2)
        for _ in range(30):
            state.key("-")
        self.assertEqual(state.speed, 0.25)
        state.key("=")
        self.assertEqual(state.speed, 0.5)
        state.key("r")
        self.assertEqual(state.elapsed, 0)
        state.key("q")
        self.assertFalse(state.running)

    def test_escape_and_control_c_exit(self):
        for key in ("\x1b", "\x03", "Q"):
            state = Playback()
            state.key(key)
            self.assertFalse(state.running)


class PainterTests(unittest.TestCase):
    def test_real_animation_deltas_reconstruct_every_character(self):
        renderer = SceneRenderer()
        width, height = 116, 36
        frames = [renderer.render(width, height, elapsed) for elapsed in (0, 0.5, 3, 6, 6, 10)]
        for mode, theme in itertools.product(("truecolor", "ansi", "none"), ("dark", "light")):
            painter = Painter(mode, theme)
            canvas = [" "] * (width * height)
            x = y = 0
            for frame in frames:
                for token in re.findall(r"\x1b\[[0-9;?]*[A-Za-z]|[^\x1b]+", painter.encode(frame)):
                    if token.startswith("\x1b["):
                        if token.endswith("H"):
                            row, column = token[2:-1].split(";")
                            x, y = int(column) - 1, int(row) - 1
                        elif token == "\x1b[2J":
                            canvas = [" "] * (width * height)
                    else:
                        for char in token:
                            self.assertLess(x, width)
                            self.assertLess(y, height)
                            canvas[y * width + x] = char
                            x += 1
                self.assertEqual(canvas, [char for char, _, _ in frame.cells])

    def test_identical_frame_produces_no_output(self):
        painter = Painter()
        frame = Frame(20, 10)
        self.assertTrue(painter.encode(frame))
        self.assertEqual(painter.encode(frame), "")

    def test_changed_and_erased_cells_use_delta_not_full_clear(self):
        painter = Painter()
        painter.encode(Frame(20, 10))
        frame = Frame(20, 10)
        frame.put(4, 3, "@", Role.HEAD)
        for changed in (frame, Frame(20, 10)):
            output = painter.encode(changed)
            self.assertIn("\x1b[4;5H", output)
            self.assertNotIn("\x1b[2J", output)
            self.assertLess(len(output), 100)

    def test_style_only_changes_are_painted(self):
        painter = Painter()
        frame = Frame(5, 3)
        frame.put(1, 1, "@", Role.HEAD)
        painter.encode(frame)
        changed = Frame(5, 3)
        changed.put(1, 1, "@", Role.EYES)
        self.assertIn("\x1b[2;2H", painter.encode(changed))

    def test_resize_clears_stale_content(self):
        painter = Painter()
        painter.encode(Frame(20, 10))
        self.assertIn("\x1b[2J", painter.encode(Frame(12, 8)))

    def test_no_color_emits_no_sgr_color_codes(self):
        frame = Frame(10, 3)
        frame.text(0, 0, TITLE, Role.TITLE)
        self.assertNotRegex(
            Painter("none").encode(frame),
            r"\x1b\[(?:3[0-9]|4[0-9]|9[0-9]|10[0-9])",
        )
        with self.assertRaises(ValueError):
            Painter("unknown")


class TerminalTests(unittest.TestCase):
    @staticmethod
    def windows_kernel():
        kernel = Mock()
        kernel.GetStdHandle.return_value = 123

        def get_mode(handle, pointer):
            pointer._obj.value = 1
            return 1

        kernel.GetConsoleMode.side_effect = get_mode
        kernel.SetConsoleMode.return_value = 1
        return kernel

    def test_terminal_restores_screen_on_exception_and_close_is_idempotent(self):
        output = io.StringIO()
        terminal = Terminal(output)
        terminal.entered = True
        with self.assertRaisesRegex(RuntimeError, "failure"):
            with patch.object(Terminal, "__enter__", return_value=terminal):
                with terminal:
                    raise RuntimeError("failure")
        terminal.close()
        self.assertEqual(output.getvalue(), LEAVE)

    def test_windows_vt_is_enabled_and_original_mode_restored(self):
        terminal = Terminal(io.StringIO())
        kernel = self.windows_kernel()
        with patch("ctypes.WinDLL", return_value=kernel, create=True):
            terminal._enable_windows_ansi()
        self.assertEqual(terminal.windows_mode, (kernel, 123, 1))
        terminal.close()
        self.assertEqual(kernel.SetConsoleMode.call_args_list, [call(123, 5), call(123, 1)])
        self.assertIsNone(terminal.windows_mode)

    def test_windows_console_failures_are_explicit(self):
        for operation in ("GetConsoleMode", "SetConsoleMode"):
            kernel = self.windows_kernel()
            getattr(kernel, operation).side_effect = None
            getattr(kernel, operation).return_value = 0
            terminal = Terminal(io.StringIO())
            with patch("ctypes.WinDLL", return_value=kernel, create=True):
                with self.assertRaises(OSError):
                    terminal._enable_windows_ansi()
            self.assertIsNone(terminal.windows_mode)

    def test_output_failure_still_restores_windows_mode(self):
        output = Mock()
        output.write.side_effect = OSError("output failure")
        terminal = Terminal(output)
        kernel = self.windows_kernel()
        terminal.entered = True
        terminal.windows_mode = (kernel, 123, 1)
        with self.assertRaisesRegex(OSError, "output failure"):
            terminal.close()
        kernel.SetConsoleMode.assert_called_once_with(123, 1)
        self.assertFalse(terminal.entered)

    def test_windows_restore_failure_is_not_silent(self):
        terminal = Terminal(io.StringIO())
        kernel = self.windows_kernel()
        kernel.SetConsoleMode.return_value = 0
        terminal.windows_mode = (kernel, 123, 1)
        with self.assertRaisesRegex(OSError, "restore"):
            terminal.close()

    def test_partial_terminal_entry_is_cleaned_up(self):
        output = Mock()
        output.write.side_effect = [OSError("setup write"), None]
        terminal = Terminal(output)
        kernel = self.windows_kernel()

        def enable():
            terminal.windows_mode = (kernel, 123, 1)

        with patch("copilot_showcase.terminal.os.name", "nt"):
            with patch.object(terminal, "_enable_windows_ansi", side_effect=enable):
                with self.assertRaisesRegex(OSError, "setup write"):
                    terminal.__enter__()
        self.assertEqual(output.write.call_args_list, [call(ENTER), call(LEAVE)])
        kernel.SetConsoleMode.assert_called_once_with(123, 1)

    def test_posix_input_mode_is_saved_and_restored(self):
        output = io.StringIO()
        termios, tty = Mock(), Mock()
        original = termios.tcgetattr.return_value
        with patch.dict(sys.modules, {"termios": termios, "tty": tty}):
            with patch("copilot_showcase.terminal.os.name", "posix"):
                with patch("copilot_showcase.terminal.sys.stdin") as stdin:
                    stdin.fileno.return_value = 17
                    with Terminal(output):
                        tty.setcbreak.assert_called_once_with(17)
        termios.tcsetattr.assert_called_once_with(17, termios.TCSADRAIN, original)
        self.assertEqual(output.getvalue(), ENTER + LEAVE)

    def test_windows_extended_keys_do_not_turn_into_exit(self):
        keyboard = Mock()
        keyboard.kbhit.side_effect = [True, True, True, False]
        keyboard.getwch.side_effect = ["\xe0", "H", "Q"]
        with patch.dict(sys.modules, {"msvcrt": keyboard}):
            with patch("copilot_showcase.terminal.os.name", "nt"):
                self.assertEqual(Terminal(io.StringIO()).keys(), ["Q"])

    def test_posix_arrow_and_escape_keys(self):
        for data, expected in ((b"\x1b[A", ["\t"]), (b"\x1b", ["\x1b"])):
            with patch("copilot_showcase.terminal.os.name", "posix"):
                with patch("copilot_showcase.terminal.select.select", side_effect=[([1], [], []), ([], [], [])]):
                    with patch("copilot_showcase.terminal.os.read", return_value=data):
                        with patch("copilot_showcase.terminal.sys.stdin") as stdin:
                            stdin.fileno.return_value = 17
                            self.assertEqual(Terminal(io.StringIO()).keys(), expected)


class CliTests(unittest.TestCase):
    def test_sculpture_is_the_only_art_and_the_default(self):
        args = parser().parse_args([])
        self.assertEqual((args.art, args.scene, args.event), ("sculpture", "orbit", DEFAULT_CAPTION))
        self.assertIn("HACKATHON", parser().format_help())
        self.assertIn("shaded Octicon", parser().format_help())
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main(["--art", "reference"])
        self.assertEqual(raised.exception.code, 2)

    def test_control_sequences_are_rejected_in_caption(self):
        for value in ("", " " * 3, "a" * 49, "Hack\x1b[2J", "Hack\n", "Hack\u00e9"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                event_name(value)
        self.assertEqual(event_name("A" * 48), "A" * 48)

    def test_nonfinite_numbers_rejected(self):
        for value in ("nan", "inf", "-inf", "hello"):
            with self.assertRaises(argparse.ArgumentTypeError):
                finite_float(value)

    def test_no_color_environment_and_explicit_override(self):
        with patch.dict(os.environ, {"NO_COLOR": ""}):
            self.assertEqual(color_mode("auto"), "none")
            self.assertEqual(color_mode("ansi"), "ansi")
            self.assertEqual(color_mode("truecolor"), "truecolor")

    def test_static_and_redirected_output_are_finite_plain_ascii(self):
        for args in (["--static"], [], ["--ascii", "--scene", "signal"]):
            output = io.StringIO()
            with contextlib.redirect_stdout(output), patch("copilot_showcase.app.animate") as animation:
                self.assertEqual(main(args), 0)
            animation.assert_not_called()
            text = output.getvalue()
            self.assertIn("Welcome to", text)
            self.assertIn(DEFAULT_CAPTION, text)
            self.assertNotIn("\x1b", text)
            self.assertTrue(text.isascii())
            self.assertEqual(len(text.splitlines()), 38)

    def test_non_tty_input_and_dumb_term_bypass_ansi_even_with_tty_output(self):
        for stdin, term in ((io.StringIO(), "xterm"), (TTYBuffer(), "dumb")):
            output = TTYBuffer()
            with patch("copilot_showcase.app.sys.stdin", stdin):
                with patch.dict(os.environ, {"TERM": term}):
                    with contextlib.redirect_stdout(output), patch("copilot_showcase.app.animate") as animation:
                        self.assertEqual(main(["--color", "truecolor"]), 0)
            animation.assert_not_called()
            self.assertNotIn("\x1b", output.getvalue())
            self.assertIn(DEFAULT_CAPTION, output.getvalue())

    def test_static_in_a_tty_is_also_ascii_and_plain(self):
        output = TTYBuffer()
        with patch("copilot_showcase.app.sys.stdin", TTYBuffer()):
            with patch.dict(os.environ, {"TERM": "xterm"}):
                with patch("copilot_showcase.app.dimensions", return_value=(38, 22)):
                    with contextlib.redirect_stdout(output), patch("copilot_showcase.app.animate") as animation:
                        self.assertEqual(main(["--static"]), 0)
        animation.assert_not_called()
        self.assertNotIn("\x1b", output.getvalue())
        self.assertTrue(output.getvalue().isascii())

    def test_screen_reader_does_not_load_or_render_art(self):
        output = io.StringIO()
        with patch("copilot_showcase.app.SceneRenderer") as renderer:
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["--screen-reader"]), 0)
        renderer.assert_not_called()
        self.assertIn("shaded mascot", output.getvalue())
        self.assertIn("HACKATHON lettering has an outline shadow", output.getvalue())
        self.assertIn("Motion and decorative output are disabled", output.getvalue())
        self.assertNotIn("\x1b", output.getvalue())

    def test_unrepresentable_title_automatically_uses_ascii(self):
        for encoding, args, expected in (("ascii", [], True), ("utf-8", [], False), ("utf-8", ["--ascii"], True)):
            output = Mock(encoding=encoding)
            output.isatty.return_value = True
            with patch("copilot_showcase.app.sys.stdout", output):
                with patch("copilot_showcase.app.sys.stdin", TTYBuffer()):
                    with patch.dict(os.environ, {"TERM": "xterm"}):
                        with patch("copilot_showcase.app.animate", return_value=0) as animation:
                            self.assertEqual(main(args), 0)
            self.assertEqual(animation.call_args.args[2], expected)

    def test_missing_art_reports_error_and_fails(self):
        error = io.StringIO()
        with patch("copilot_showcase.app.SceneRenderer", side_effect=FileNotFoundError("missing asset")):
            with contextlib.redirect_stderr(error):
                self.assertEqual(main(["--static"]), 1)
        self.assertIn("Cannot run the screensaver: missing asset", error.getvalue())

    def test_terminal_failure_reports_error_and_fails(self):
        error = io.StringIO()
        with patch("copilot_showcase.app.sys.stdin", TTYBuffer()):
            with patch.dict(os.environ, {"TERM": "xterm"}):
                with contextlib.redirect_stdout(TTYBuffer()), contextlib.redirect_stderr(error):
                    with patch("copilot_showcase.app.animate", side_effect=OSError("console failure")):
                        self.assertEqual(main([]), 1)
        self.assertIn("Cannot run the screensaver: console failure", error.getvalue())

    def test_argument_boundaries(self):
        invalid = (
            ["--fps", "4"], ["--fps", "61"], ["--speed", "0.24"], ["--speed", "2.01"],
            ["--duration", "0"], ["--duration", "-1"], ["--duration", "nan"],
        )
        for args in invalid:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                main(args)
            self.assertEqual(raised.exception.code, 2)


class AnimationTests(unittest.TestCase):
    def setUp(self):
        self.clock = 0.0
        self.args = parser().parse_args(["--duration", "0.2"])
        self.renderer = Mock(spec=SceneRenderer)
        self.renderer.render.return_value = Frame(20, 10)
        self.terminal = Terminal(io.StringIO())

    def run_animation(self, keys=None, sizes=None):
        def enter(terminal):
            terminal.entered = True
            return terminal

        def sleep(delay):
            self.clock += max(delay, 0.001)

        previous = object()
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch("copilot_showcase.app.Terminal", return_value=self.terminal))
            stack.enter_context(patch.object(Terminal, "__enter__", enter))
            stack.enter_context(patch.object(self.terminal, "keys", side_effect=keys or itertools.repeat([])))
            stack.enter_context(patch("copilot_showcase.app.dimensions", side_effect=sizes or itertools.repeat((20, 10))))
            stack.enter_context(patch("copilot_showcase.app.time.monotonic", side_effect=lambda: self.clock))
            stack.enter_context(patch("copilot_showcase.app.time.sleep", side_effect=sleep))
            stack.enter_context(patch("copilot_showcase.app.signal.getsignal", return_value=previous))
            self.handler = stack.enter_context(patch("copilot_showcase.app.signal.signal"))
            try:
                return animate(self.args, self.renderer, True)
            finally:
                self.assertEqual(self.handler.call_args, call(signal.SIGTERM, previous))
                self.assertTrue(self.terminal.output.getvalue().endswith(LEAVE))

    def test_duration_uses_wall_clock(self):
        self.assertEqual(self.run_animation(), 0)
        self.assertGreaterEqual(self.clock, 0.2)
        self.assertGreater(self.renderer.render.call_count, 1)

    def test_paused_frames_do_not_repaint_and_duration_still_expires(self):
        keys = itertools.chain([[" "]], itertools.repeat([]))
        self.assertEqual(self.run_animation(keys), 0)
        self.assertEqual(self.renderer.render.call_count, 1)
        self.assertEqual(self.renderer.render.call_args.args[2], 0)
        self.assertTrue(self.renderer.render.call_args.args[7])
        self.assertGreaterEqual(self.clock, 0.2)

    def test_resize_still_renders_while_paused(self):
        keys = itertools.chain([[" "]], itertools.repeat([]))
        self.assertEqual(self.run_animation(keys, [(20, 10), (21, 10)]), 0)
        self.assertEqual([item.args[:2] for item in self.renderer.render.call_args_list], [(20, 10), (21, 10)])
        self.assertTrue(all(item.args[2] == 0 for item in self.renderer.render.call_args_list))

    def test_quit_does_not_render_another_frame(self):
        self.assertEqual(self.run_animation([["q"]]), 0)
        self.renderer.render.assert_not_called()

    def test_sigterm_requests_orderly_exit(self):
        def terminate():
            self.handler.call_args.args[1](signal.SIGTERM, None)
            return []

        self.assertEqual(self.run_animation(terminate), 0)
        self.renderer.render.assert_not_called()

    def test_keyboard_interrupt_restores_terminal_and_returns_success(self):
        self.renderer.render.side_effect = KeyboardInterrupt
        self.assertEqual(self.run_animation(), 0)

    def test_render_failure_restores_terminal_and_signal_handler(self):
        self.renderer.render.side_effect = ValueError("render failure")
        with self.assertRaisesRegex(ValueError, "render failure"):
            self.run_animation()


class PackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="screensaver-test-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.base = Path(cls.temporary.name)
        cls.clean = cls.base / "clean source"
        cls.output = cls.base / "packaged demo"
        cls.outside = cls.base / "unrelated working directory"
        cls.outside.mkdir()
        cls.env = {key: value for key, value in os.environ.items() if key not in ("PYTHONPATH", "PYTHONHOME")}
        cls.env.update(PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1", TERM="dumb")
        source_files = RUNTIME_FILES | {Path("screensaver.py"), Path("README.md"), Path("tools", "package_demo.py")}
        for relative in source_files:
            target = cls.clean / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        (cls.clean / "copilot_showcase" / "unshipped.txt").write_text("Do not package extra files.", encoding="ascii")
        cls.archive = cls.output / "copilot-screensaver.pyz"
        result = cls.python(cls.clean / "tools" / "package_demo.py", "--output", cls.output)
        if result.returncode:
            raise AssertionError(f"Packaging failed:\n{result.stdout}\n{result.stderr}")

    @classmethod
    def python(cls, *args, cwd=None):
        return subprocess.run(
            [sys.executable, "-S", *map(str, args)], cwd=cwd or cls.outside,
            env=cls.env, capture_output=True, text=True, encoding="utf-8", timeout=20,
        )

    def assert_plain_success(self, result, screen_reader=False):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertNotIn("\x1b", result.stdout)
        self.assertTrue(result.stdout.isascii())
        self.assertIn(TITLE if screen_reader else "Welcome to", result.stdout)
        self.assertIn(DEFAULT_CAPTION, result.stdout)

    def test_clean_source_default_needs_only_approved_files(self):
        for args in ([], ["--static"], ["--screen-reader"]):
            with self.subTest(args=args):
                result = self.python(self.clean / "screensaver.py", *args)
                self.assert_plain_success(result, "--screen-reader" in args)
        self.assert_plain_success(self.python("-m", "copilot_showcase", cwd=self.clean))

    def test_archive_uses_an_exact_allowlist_and_retains_the_license(self):
        with zipfile.ZipFile(self.archive) as archive:
            names = {member.filename for member in archive.infolist() if not member.is_dir()}
            self.assertEqual(names, {path.as_posix() for path in RUNTIME_FILES} | {"__main__.py"})
            self.assertEqual(
                archive.read("copilot_showcase/assets/LICENSE-Octicons.txt"),
                (ROOT / "copilot_showcase" / "assets" / "LICENSE-Octicons.txt").read_bytes(),
            )
        self.assertEqual(
            {path.name for path in self.output.iterdir()},
            {"copilot-screensaver.pyz", "Start-Screensaver.cmd", "README.md", "LICENSE-Octicons.txt"},
        )

    def test_packaged_default_static_and_screen_reader_work_without_site_packages(self):
        for args in ([], ["--static"], ["--screen-reader"]):
            with self.subTest(args=args):
                self.assert_plain_success(self.python(self.archive, *args), "--screen-reader" in args)
        self.assertEqual(self.python(self.archive, "--art", "reference").returncode, 2)
        self.assertEqual(self.python(self.archive, "--duration", "0").returncode, 2)

    def test_packaging_default_is_local_to_the_demo_not_a_personal_folder(self):
        config = runpy.run_path(str(self.clean / "tools" / "package_demo.py"))
        self.assertEqual(config["DEFAULT_OUTPUT"], (self.clean / "dist").resolve())
        self.assertFalse((self.clean / "dist").exists())

    def test_missing_packaged_material_map_fails_instead_of_falling_back(self):
        with tempfile.TemporaryDirectory(dir=self.base) as temporary:
            broken = Path(temporary) / "copilot-screensaver.pyz"
            with zipfile.ZipFile(self.archive) as source, zipfile.ZipFile(broken, "w") as target:
                for member in source.infolist():
                    if member.filename != "copilot_showcase/assets/copilot.json":
                        target.writestr(member, source.read(member))
            result = self.python(broken, "--static")
            self.assertEqual(result.returncode, 1)
            self.assertIn("Cannot run the screensaver:", result.stderr)
            self.assert_plain_success(self.python(broken, "--screen-reader"), screen_reader=True)
            if os.name == "nt":
                launcher = Path(temporary) / "Start-Screensaver.cmd"
                shutil.copy2(self.output / launcher.name, launcher)
                result = subprocess.run(
                    [os.environ["COMSPEC"], "/d", "/c", "call", str(launcher), "--static"],
                    cwd=self.outside, env=self.env, capture_output=True, text=True,
                    encoding="utf-8", timeout=20,
                )
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    @unittest.skipUnless(os.name == "nt", "The .cmd launcher is Windows-only.")
    def test_windows_launcher_preserves_success_and_argument_error_exit_codes(self):
        launcher = self.output / "Start-Screensaver.cmd"
        for args, expected in ((["--screen-reader"], 0), (["--fps", "0"], 2)):
            result = subprocess.run(
                [os.environ["COMSPEC"], "/d", "/c", "call", str(launcher), *args],
                cwd=self.outside, env=self.env, capture_output=True, text=True,
                encoding="utf-8", timeout=20,
            )
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
