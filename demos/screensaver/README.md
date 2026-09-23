# Hackathon terminal screensaver

An **optional, offline workshop demo**: a shaded mascot sculpture beside large
HACKATHON lettering with an outline shadow, a "Welcome to" greeting, and a
"LET'S BUILD" caption. The sculpture uses the MIT-licensed Primer Octicons
asset described below. This is an independent animation, not a reproduction
of the GitHub Copilot CLI banner.

It runs in one local Python process. No pip packages, network requests,
GitHub login, Copilot subscription, or changes to onboarding tools are needed.
It does not install an OS screensaver or change terminal profiles, power
settings, or Copilot settings.

## Install and run

Install **Python 3.10 or newer** from [python.org](https://www.python.org/downloads/).
Ensure Python is on your PATH, reopen your terminal, and check `python --version`.
The examples below use PowerShell; on macOS/Linux use `python3` and your shell's
native path separators.

From the repository root:

```powershell
cd .\demos\screensaver
python .\screensaver.py
```

`python -m copilot_showcase` is an equivalent entry point from this directory.
Press **Q**, **Escape**, or **Ctrl+C** to exit.

Use a monospaced terminal with ANSI support, such as Windows Terminal.
The full artwork needs at least **39 columns by 23 rows**. Smaller terminals
show a compact text message instead. At **113 columns by 25 rows** or larger,
the mascot and title sit side by side; otherwise they stack. The title uses
46 cells, or a complete 37-cell variant in narrow panes, without dropping letters.

```powershell
python .\screensaver.py --event "HACKATHON 2026"
python .\screensaver.py --scene tour --speed 0.5
python .\screensaver.py --duration 300
```

The mascot enters, then continues turning and floating rather than replaying a
fixed set of frames. `--duration` limits real elapsed seconds, even while paused.
Without it, interactive animation runs until you exit. `--event` accepts 1-48
printable ASCII characters; long captions are clipped to fit a narrow terminal.
`--fps` sets a ceiling from 5 to 60 frames per second (default: 24).
`--seed` makes the starfield reproducible.

## Controls

| Key | Action |
| --- | --- |
| Space | Pause/resume motion and the automatic scene clock |
| R | Replay the entrance |
| 1 | Orbit: drifting stars and an orbital ring (default) |
| 2 | Warp: moving star trails and stronger rotation |
| 3 | Signal: drifting stars, ring, and a scanning light |
| Tab | Next scene |
| A | Auto-tour: change scenes every 24 animation seconds |
| C | Cycle truecolor, terminal ANSI colors, and monochrome |
| + / - | Adjust motion speed from 0.25x to 2x |
| H | Show/hide controls |
| Q / Escape / Ctrl+C | Exit |

Auto-tour timing scales with motion speed. Pause freezes the sculpture,
starfield, and tour; help, resize, color changes, and exit still work.

## Accessibility and terminal compatibility

```powershell
python .\screensaver.py --theme light
python .\screensaver.py --color ansi
python .\screensaver.py --color none
python .\screensaver.py --ascii
python .\screensaver.py --static
python .\screensaver.py --screen-reader
```

The normal title uses Unicode blocks and box-drawing characters; the shaded
sculpture uses printable character density. `--ascii` also converts the title
and shadow to printable ASCII. An output encoding that cannot represent the
title automatically selects that fallback.

`--static`, redirected input or output, and `TERM=dumb` produce **one finite
plain ASCII frame**, with no ANSI control sequences. `--screen-reader` prints
only a plain-language description and does not load or render the artwork.
These modes avoid motion entirely. Interactive `--color none` removes colors,
but still uses ANSI cursor positioning.

`NO_COLOR` disables automatic color selection; an explicit `--color` takes
precedence. ANSI and monochrome modes inherit the terminal background; truecolor
sets a dark or light background according to `--theme`.

Normal exits, handled exceptions, and SIGTERM leave the alternate screen, show
the cursor, re-enable wrapping, and restore saved Windows console or POSIX
input modes. Forced process termination and terminal crashes cannot run cleanup.
If Windows cannot enable virtual-terminal output, the demo reports an error
instead of emitting a broken animation; use Windows Terminal or `--static`.

Exit codes: **0** for normal output/interactive exit, **1** for runtime or
artwork failures, and **2** for invalid arguments. `--art sculpture` is accepted
for clarity and compatibility; it is the only supported artwork mode.
Missing artwork is an error, not a request to download or silently substitute it.

## Tests

From `demos\screensaver`:

```powershell
python -m unittest discover -s tests -v
```

The suite exercises both lettering widths, all scenes, keyboard playback,
changed-span painting, terminal cleanup, CLI fallbacks and errors, and fresh
source/zipapp runs with `python -S`. Packaging tests use temporary directories
and verify an explicit archive file allowlist, including the MIT notice.
There are no third-party test dependencies.

## Portable packaging

From `demos\screensaver`:

```powershell
python .\tools\package_demo.py --output .\dist
python -S .\dist\copilot-screensaver.pyz --static
python -S .\dist\copilot-screensaver.pyz --screen-reader
.\dist\Start-Screensaver.cmd --duration 60
```

Without `--output`, the builder uses this demo's ignored `dist` directory,
regardless of the caller's working directory. A different `--output` directory
is supported. The builder uses only the Python standard library and emits:

- `copilot-screensaver.pyz`: the entry point, runtime modules, and licensed assets.
- `Start-Screensaver.cmd`: a Windows launcher forwarding arguments and exit codes.
- `README.md` and `LICENSE-Octicons.txt`: usage and the asset license.

You can move the output directory anywhere. The archive still requires Python
3.10+; it is not a bundled Python interpreter. On any supported platform,
`python copilot-screensaver.pyz` runs it without the source checkout or pip.
The `.cmd` launcher tries `py -3`, then `python` if the Windows Python launcher
is absent. Source-only test and build commands above are not part of the archive.

Only explicitly listed runtime files enter the archive, not tests, caches,
other assets, development tools, or media. Do not commit generated archives.
The [architecture notes](docs/architecture.md) are in the source checkout;
no external diagram generator or installed skill is required.

## Attribution and rights

`copilot_showcase\assets\copilot.svg` and its derived `copilot.json` material map
come from **Primer Octicons v19.15.3**, **Copyright (c) 2025 GitHub Inc.**,
under the **MIT license**. See the
[pinned source icon](https://github.com/primer/octicons/blob/v19.15.3/icons/copilot-96.svg)
and the retained [LICENSE-Octicons.txt](copilot_showcase/assets/LICENSE-Octicons.txt).
Keep that notice with copies and substantial portions of these assets.
The generic HACKATHON bitmap lettering, relief lighting, and motion are custom
demo code; the mascot remains GitHub's Copilot character, not unbranded artwork.

The asset's MIT license **does not grant trademark rights or GitHub brand
approval**. This demo is not an official GitHub product, logo, or branding kit
and does not imply GitHub endorsement.
[GitHub's mascot guidance](https://brand.github.com/graphic-elements/mascots#usage)
requires Brand & Marketing Design team approval for public-facing mascot use;
obtain that approval separately before such use.

No blog-derived animation frames, recordings, reference images, screenshots,
or reference renderer are included or required.
