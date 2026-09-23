# Screensaver architecture

This optional demo is one local Python process with no runtime dependencies
outside the standard library, no network requests, and no connection to the
onboarding app or GitHub Copilot CLI.

## Rendering pipeline

```text
Primer Octicons v19.15.3 SVG (bundled provenance; not parsed at runtime)
  -> pre-baked copilot.json material map
  -> art.load_mesh(): points, surface normals, material roles
  -> SceneRenderer + lettering: projection, lighting, stars, title and caption
  -> Frame: cells of (character, semantic role, brightness 0-15), plus depth
  -> Painter.encode(): changed row spans, grouped ANSI styles
  -> Terminal.output: one write/flush per changed frame
  -> terminal emulator

app.Playback: monotonic clock + keyboard state -> SceneRenderer / Painter
app.main: CLI + terminal capability checks -> animation OR plain-text output
```

The material map and SVG retain the MIT Octicons notice. The map contains a
96 by 96 sampling grid; `load_mesh` validates dimensions/material values and
builds front and back relief surfaces once at startup. The SVG is retained
for attribution and source provenance, not downloaded or decoded during playback.

`SceneRenderer` transforms positions and normals, applies perspective and a
depth test, and maps lighting to printable characters and color brightness.
Orbit, warp, and signal share the sculpture but vary its movement, starfield,
ring, or scanning light. The title comes from original HACKATHON bitmap glyphs
in `lettering.py`, packed into 46-cell or 37-cell rows with an outline shadow.
Wide terminals place the title beside the mascot; smaller ones stack them.
Undersized terminals get a bounded text fallback.

## Clock, keyboard, and output

`Playback` owns elapsed animation time, pause/help flags, scene, speed, color,
and the running flag. The default scene is orbit; optional tour mode advances
every 24 animation seconds. Speed affects that clock, pause freezes it, and R
resets it to replay the entrance. The sculpture then moves continuously; there
is no stored frame sequence or fixed final-pose hold.

`animate` caps frame rate, bounds a single clock step after a stall, responds
to keyboard input and resize, and uses real monotonic time for `--duration`.
Paused frames are not recomposed unless their state or terminal size changes.
Frame dimensions reserve the terminal's last row/column and are capped at
220 by 75 cells.

`Painter` keeps the previous frame. For each changed row it finds the first
and last changed cells, emits one cursor move, groups consecutive styles, and
returns one output string. Identical frames return an empty string. Screen
clearing is limited to startup, resize, or resetting the painter for a color
mode change, rather than every animation frame.

`Terminal` manages the alternate screen, cursor visibility, wrapping, and input.
On Windows it saves the console mode, enables virtual-terminal output, and
restores the saved mode. On POSIX it saves input settings and uses cbreak mode.
Context-manager cleanup runs on normal exit and exceptions; SIGTERM requests
an orderly exit. Uncatchable termination cannot guarantee cleanup.

Static mode, non-TTY input/output, and `TERM=dumb` bypass terminal setup and ANSI
painting and print one ASCII frame. Screen-reader mode bypasses asset loading
as well, printing only a description. Unsupported CLI values fail with exit 2;
missing/invalid artwork or terminal failures report an error and exit 1.

## Packaging boundary

`tools\package_demo.py` copies an explicit runtime allowlist into temporary
staging and uses `zipapp` to build a portable `.pyz`. `importlib.resources`
loads the same material map from a checkout or directly from that archive.
The Windows launcher preserves the Python process's exit status.

Only the Python runtime modules, entry point, and MIT-licensed assets enter
the archive. Documentation and the license accompany it. No development
libraries, installed skills, generated viewers, recordings, reference frames,
or media are needed. Unit tests check both lettering widths, delta output
reconstruction, cleanup, and fresh-directory source/archive execution with
site packages disabled.
