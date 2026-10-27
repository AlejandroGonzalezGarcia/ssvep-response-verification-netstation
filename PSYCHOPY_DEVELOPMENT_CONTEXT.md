# Reusable PsychoPy engineering context

Updated: 2026-10-22. Canonical location: `eeg-projects/PSYCHOPY_DEVELOPMENT_CONTEXT.md`.
Read this together with the destination project's instructions, protocol, live
configuration and validation record. This guide concerns **PsychoPy presentation**:
displays, spatial calibration, timing, input, portability, diagnostics and cleanup.
It is independent of acquisition device, vendor, transport and recording architecture.
A future experiment can use it without EEG, LSL or any existing lab runtime.
Copy this file together with `NETSTATION.md` into a new repository when using
NetStation. Both documents are self-contained engineering contracts; references to
originating project code are optional implementation examples, not runtime dependencies.
They remove repeated setup decisions but do not supply an executable starter framework.
Implement or deliberately vendor the reusable infrastructure, then develop the study's
simulation and validate it on the intended station.

## Start a new project without repeating setup decisions

- Inspect the requested template, station configuration, environment and existing
  code first. Reuse established engineering choices and already supplied measurements
  when the same station/monitor/setup is intended. Do not ask the scientist to repeat
  information discoverable in the project. Revalidate that it matches the actual display.
- Keep the new experiment independent. Reuse reviewed presentation components;
  do not import another experiment's presentation package, copy recordings, upgrade
  its environment, or edit shared acquisition infrastructure incidentally.
- Separate **study protocol** (stimuli, conditions, units, waveform, phase policy,
  durations, tasks, responses) from **station calibration** (monitor, screen selection,
  resolution, physical dimensions, distance, refresh) and optional acquisition adapters.
- Carry over the requested template's scientific choices exactly. Ask only for missing
  measurements or scientifically consequential choices that cannot be inferred from
  the requested protocol/template. Never silently change stimulus geometry or timing.
- Engineering defaults for a new project: fullscreen participant window, explicit
  monitor selection, synchronous flips, main-thread drawing, preloaded stimuli,
  Escape abort, persistent diagnostics, unique run directories, and a genuine
  presentation-only mode. Operator keys and response tasks follow the study.
- Provide separate tools for config validation, monitor listing, display/timing check,
  geometry preview and short simulation pilot. Keep development controls away from
  the ordinary participant launcher. Validation/listing must not start acquisition.

## Environment and compatibility

The current reference is `ssvep-mapping-netstation`, using `psychopy2026`:
Python 3.10.21, PsychoPy 2026.1.3, pyglet 1.5.27, NumPy 2.2.6, Pillow 10.4.0,
and PyYAML 6.0.2. These are reviewed local versions, not a claim of latest releases.
Inspect the selected interpreter and dependency manifest; shell `python3` need not
point to this environment. `environment_context.md` in the reference project is an
older Linux/PsychoPy 2025 snapshot, not the current environment specification.

No application-level `import pyglet`, `winType="pyglet"`, native Cocoa/Retina patches,
private framebuffer access or OpenGL viewport repair is required by this baseline.
PsychoPy may internally use pyglet; avoiding direct pyglet calls does not remove its
backend dependency. Reuse the public PsychoPy API and the tested environment.

On an existing station, reuse its tested environment. For a new Linux station,
provision an OS/architecture-appropriate environment compatible with the intended
PsychoPy/backend versions; never copy a macOS environment. Revalidate any deliberate
version migration. Native graphics and GUI dependencies depend on distribution and
release; package pins alone do not install them. See the official
[installation guide](https://psychopy.org/download.html), distinguishing its current
release instructions from this project's pinned stack. Acquisition libraries are
optional dependencies, not prerequisites for pure presentation tools.

## Default participant display and calibration

Use these explicit defaults for new simulations on this lab station:

```yaml
display:
  screen_index: 1
  resolution_px: [1920, 1080]
  refresh_rate_hz: 60.0
  fullscreen: true
  width_cm: 53.5
  height_cm: 30.1
  viewing_distance_cm: 57.6
```

“Monitor 1” means PsychoPy **`screen=1`**, the zero-based second display. The
`monitor=` argument is a calibration object/profile, not a display index; do not
pass `monitor=1` to select the screen. If a project's configuration calls its index
`monitor`, map that value to `Window(screen=...)` explicitly. Retain these station
measurements on this same setup; a different physical panel/distance needs its own
calibration. Spatial units and stimulus parameters remain protocol decisions.

Minimal public-API window construction (not a full experiment or timing check):

```python
from psychopy import monitors, visual

calibration = monitors.Monitor("lab-participant-display", width=53.5, distance=57.6)
calibration.setSizePix([1920, 1080])
win = visual.Window(
    size=[1920, 1080], screen=1, monitor=calibration,
    fullscr=True, units="pix", waitBlanking=True,
    checkTiming=False, autoLog=False, allowGUI=False,
)
try:
    if list(map(int, win.size)) != [1920, 1080]:
        raise RuntimeError(f"Configured 1920x1080; observed {win.size}")
    # Run the startup refresh check below before beginning the simulation.
    # Select study-specific units explicitly when constructing stimuli.
finally:
    win.close()
```

Use the same size and refresh guards in test and acquisition modes. Request the
configured size directly; compare public `Window.size` before constructing stimuli
and after refresh measurement. Fail with configured/observed values on mismatch.
Never silently select screen 0, adopt laptop dimensions, alter calibration, or add
native/pyglet workarounds to make a failed check pass. This supersedes the older
mapping cache/viewport-repair guidance; the current reference has no such fixes.

60 Hz is a requested expectation and scheduling default, not something window size
or a Python variable forces the display to deliver. Configure the OS display mode
accordingly and measure refresh with the procedure below. Screen indices can change
after hotplug/layout changes. Confirm fullscreen placement and physical geometry on
the actual panel. Public window size and screenshots do not prove monitor identity,
photon timing or physical scale. Record configured/observed size, refresh evidence,
physical active dimensions (excluding bezels), viewing distance and operator checks.
The reference uses a 1% physical/pixel aspect tolerance for square pixels.

## Spatial units are a study decision

| Units | Intended interpretation |
| --- | --- |
| `pix` | Framebuffer pixel geometry; useful for calibrated edge patches. |
| `cm` | Physical dimensions using monitor calibration. |
| `deg` | Conventional visual-angle conversion; no eccentric flat-screen correction. |
| `degFlatPos` | Flat-screen correction for position, without the corresponding size correction. |
| `degFlat` | Flat-screen correction for position and vertices/size. |
| `height` / `norm` | Relative window coordinates, useful for instructions; not physical calibration. |

See PsychoPy's [units documentation](https://psychopy.org/general/units.html).
Do not substitute `degFlat` for `degFlatPos`: they express different protocols.
Inspect the entire rendered extent, not just the center; maintain image aspect ratio
and content identity. Do not clip, shrink or change eccentricities automatically to
fit a monitor. A textured image's internal projection can still be an approximation.

If a photodiode patch is requested, define its size, location and modulation explicitly.
For an edge-anchored physical patch, convert cm with the selected framebuffer's
pixels/cm and check all bounds. Record its screen position; a patch at another
vertical location does not establish identical photon onset at the stimulus location.

## Frame timing and waveform policy

Draw and flip on the main thread. Preload images, textures, text and reusable objects;
use `autoLog=False` for objects updated each frame. Keep file access, printing,
serialization, networking, blocking waits and expensive allocation out of timed loops
and flip callbacks. Optional workers must not touch the PsychoPy window.

For the existing frame-synchronous visual paradigms, retain these lab startup defaults
unless the protocol explicitly establishes different criteria:

- 60 warmup flips, followed by 120 measured frame intervals.
- Finite positive intervals, interval SD at most 0.2 ms, no interval above 1.5 × mean,
  and measured/configured refresh difference at most 1%.
- Flicker frequencies strictly below half the measured refresh. This is a minimum
  sampling check, not proof that every requested waveform is reproduced accurately.

Persist the actual measurement, including rejected attempts. Explain failures and
fix the display/session/load cause rather than weakening thresholds. Configured Hz
is an expectation, not a measured refresh result. Recheck under intended acquisition
and rendering load. Startup regularity alone does not establish physical onset timing.

Make the phase/timebase and rounding rule explicit in each project:

- **Frame-indexed phase:** value for frame n is derived from n and the selected refresh
  basis. A delayed flip stretches the displayed sequence in time. Mapping deliberately
  uses configured refresh and Python `round(seconds × refresh)` (ties to even).
- **Elapsed-time phase:** derive the next value from predicted flip time relative to
  the actual first flip, then retain actual timestamps. A delayed frame advances phase.
  Horizontal/radial use this approach and `floor(seconds × measured_refresh + .5)`.
- These are alternatives, not interchangeable improvements. Preserve the requested
  template. For a new periodic-stimulation protocol without a stated policy, resolve
  this scientific choice once; do not hide it in a shared helper or assume mapping's
  policy applies universally.

Record requested duration, rounding rule, planned/actual frame count, first stimulus
flip, first removal flip, frame intervals, long frames and estimated missed refreshes.
Include the last stimulus frame's held interval through removal. Preserve phase reset,
waveform, modulation range, contrast/opacity semantics and trial order. No automatic
repeat/rejection unless prescribed by the protocol.

Use `Window.timeOnFlip` for software flip records and lightweight `callOnFlip` callbacks
for visual-event publication. Keep predicted and actual times distinguishable. Neither
a flip timestamp nor a callback is a photodiode measurement. Hardware/driver/compositor
latency can remain invisible in frame logs; validate physical timing on the actual
station. See [PsychoPy timing guidance](https://psychopy.org/general/timing/millisecondPrecision.html)
and the [Window API](https://psychopy.org/api/visual/window.html).

## Keyboard and response timing

Use a small backend-aware adapter. Record the actual keyboard backend. The installed
2026.1.3 `event` fallback was observed to mishandle timestamped name pairs/filtering and
multiple queued events through the higher-level path; do not generalize this defect
to every version. For that fallback, call `event.getKeys` directly and process every
returned pair. For other backends, use `Keyboard.getKeys(waitRelease=False, clear=True)`.

Use one explicitly chosen PsychoPy clock for software flips and timestamped responses:
pass it to `Keyboard(clock=...)` and `event.getKeys(timeStamped=...)`; interpret `k.rt`
relative to that clock. If resetting a response clock per trial, record the origin
and convert explicitly before comparison. Do not timestamp an event when it is polled
or discard all but the first queued key. See the [Keyboard API](https://psychopy.org/api/hardware/keyboard.html).

Normalize Enter/keypad Enter to Return. Clear stale keys once on entering operator
screens, not on every frame. Poll throughout instructions, trials, breaks and startup
measurements. Keep Escape available; do not use `waitKeys`, sleeps or terminal input
in a timed presentation loop. Respect window focus and validate physical keys after
using a terminal. Simulation/injected events do not validate human response latency.
Preserve the study's scoring windows, hit/miss/false-alarm rules and response hardware.

## Acquisition-independent boundaries and clock provenance

The presentation layer owns stimuli, software flip/response timing, event identity
and local diagnostics. Optional acquisition/trigger adapters own their own connection,
clock conversion, metadata, worker health and finalization. Do not embed device names,
channel layouts, sample rates, serial ports or a required three-process architecture
in reusable PsychoPy code. Follow the requested project's acquisition contract.

- Presentation-only mode must not import acquisition libraries, open device/stream
  connections, or show recorder-dependent prompts; retain local diagnostics and
  explicitly label untransmitted events.
- Keep each clock domain named. Device time, sample index, PsychoPy time, wall time
  and transport time are not interchangeable. Pair clocks/calibration only through
  a documented synchronization mechanism. Do not silently repair, sort or clamp
  timestamps to make data appear aligned.
- If LSL is selected, obtain the visual event's LSL timestamp inside the flip callback
  with `local_clock()`, and retain its separate PsychoPy flip time. Confirm same-host
  clock assumptions; remote-host samples need explicit synchronization policy.
  Successful event publication is not proof of downstream recording or alignment.
- Acquisition work must stay outside the drawing thread. Surface worker failures
  promptly with precise reasons. Integrate the requested readiness requirement before
  study start; permit presentation-only bypass only when explicitly selected.
- Clear the stimulus first on abort/failure, then finalize owned acquisition resources
  and diagnostics. Attempt independent cleanup even after another cleanup failure.
  Wait for accepted data to flush before saying saving succeeded; report failures.
  Never stop externally owned streamers unless the task explicitly assigns that ownership.

A stream with a matching name or correct sample shape can still have invalid timing.
Timestamp diagnostics should distinguish wrong width, non-finite values, missing data,
and duplicate/backward times with the relevant previous/current values. This is an
adapter concern; do not reinterpret it as a PsychoPy display defect. Transport/sample
schema and device-specific policy belong in the project handoff, not this guide.

## Linux laboratory commissioning

Linux is a deployment target requiring its own evidence; macOS success is not Linux
validation. The existing pyglet 1.5.27 path is designed around a local X11 graphical
session and an extended desktop on one X screen. This is a lab reference setup,
not a claim that PsychoPy universally requires X11. Wayland/XWayland and other
backends need separate selection, input and timing checks on the actual machine.

1. Record distribution/version, architecture, Python/PsychoPy/pyglet versions, GPU and
   OpenGL renderer/driver, desktop/compositor, session type, monitor inventory, scaling,
   native mode and refresh. Read `XDG_SESSION_TYPE`, `DISPLAY`, `WAYLAND_DISPLAY`.
   Where installed, `xrandr --query` (X11) and `glxinfo -B` are useful read-only diagnostics;
   they do not replace public window-size and physical-placement checks. Do not invent session environment
   values, run the experiment as root, or alter graphics settings automatically.
2. Use an interactive local desktop with working graphics access. A headless/SSH run,
   virtual display, software renderer or remote-desktop session does not certify timing.
   Resolve system dependencies for the actual distro and pinned release. Do not paste
   old cross-distribution repositories or wheel commands without verifying compatibility.
3. Attach all monitors, request `screen=1` through PsychoPy, then check public
   window size, visible placement and measured refresh. No direct pyglet display
   enumeration or private native-window access is part of the default application.
   Resolve an unavailable or misidentified screen through the station setup; do not
   silently change `DISPLAY`, switch screens or introduce backend patches.
4. Start commissioning with native panel resolution, fixed refresh and 100% scaling
   where practical. Record changes to compositor, variable-refresh, display processing,
   power/blanking and driver settings; remeasure after each relevant change. Test with
   both monitors attached, including mixed-refresh cases. Do not disable a compositor
   globally or declare Wayland safe/unsafe without measurements on that setup.
5. Verify physical dimensions/distance, central and edge targets, fixation and any
   photodiode patch. Then run warmup/refresh checks and the representative stimulus
   workload. Repeat with intended acquisition load. Inspect dropped frames and use
   physical timing hardware for latency/waveform validation.
6. Check focused physical keys, start/break/abort/completion, multiple queued responses,
   output permissions, and clean exit. Paths are case-sensitive: use portable pathlib
   paths relative to the config/project and avoid macOS-specific native APIs on Linux.
7. Save the station profile and evidence. Recommission after driver/OS/backend updates,
   monitor replacement, cabling/layout/scaling changes or response-device changes.

The current repository has simulated Linux cases but **no documented physical Linux
multi-monitor commissioning**. Preserve that limit until actual evidence is recorded.

## Output, checks and handoff for every new experiment

Keep unique, non-overwritten runs. Save the source/resolved configuration, station
profile, asset identity/hash when applicable, seed and planned schedule, software
versions, configured/observed display size and refresh, placement checks, keyboard backend, software timing,
events and final/partial status. Checkpoint outside timed phases. Document what can
be lost in a hard crash; individually atomic files do not make a run transactional.
Preserve begun-but-incomplete trials and historical records.

Acceptance should progress from pure checks to hardware:

1. Config/schedule/geometry/waveform math and failure cases; keyboard adapters with
   multiple queued events; test mode with acquisition dependencies unavailable.
2. Real-window display check and geometry preview on the intended monitor; short
   software pilot through trials, breaks, Escape, completion and startup failures.
3. Physical-key checks and representative-load timing; acquisition integration only
   when requested; physical display/response timing validation for collection.

Record dates, commands, versions, config, results and limitations in the destination
handoff. Use actual test results, not older pass counts. Distinguish sandbox/session
access failures from application bugs; PsychoPy may need its normal preferences
permissions. Do not change HOME, patch site-packages or disable checks to force a run.

## Reference code and present limitations

The originating implementation is `eeg-projects/ssvep-mapping-netstation/`.
Its `mapping/display.py`, `mapping/controls.py`, `mapping/config.py`, `tools.py`,
`README.md`, `AI_CONTEXT.md` and `VALIDATION.md` describe the current public-API
baseline. Review source before reusing components; do not import the whole sibling
experiment into a new repository. The older `ssvep-mapping` native-window machinery
is not the baseline for this handoff. Study units (`degFlatPos` in that experiment),
flicker, fixation task, gray periods and photodiodes are not universal defaults.

Existing reference commands, run from its project directory:

```bash
conda activate psychopy2026
python -B tools.py validate
python -B tools.py doctor
python -B tools.py check-display
python -B tools.py preview-geometry
python -B tools.py pilot --participant SOFTWARE_PILOT
```

These are commands supplied by the reference project, not scripts embedded in this
file. Provide equivalent tools in the new repository. Validate/doctor are offline;
check-display/preview open a real window; pilot is presentation-only and saves data.

The reference's 2026-10-19 monitor recheck passed at 1920 × 1080 on screen 1,
59.99956 Hz with interval SD 0.05772 ms. Two short real-window production-scheduler
pilots completed with no long intervals or estimated missed refreshes. That evidence
supports this display baseline on the tested setup; it does not establish physical
photodiode/DIN/EEG timing, new-study performance or Linux commissioning. No hardware
or display test was run for this 2026-10-22 documentation update.

Preserve each new study's protocol and record its own software, real-window and
physical acceptance evidence. Keep device-specific details in `NETSTATION.md` and
study-specific choices in the destination project's configuration and handoff.
