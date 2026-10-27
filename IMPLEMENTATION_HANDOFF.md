# Central SSVEP experiment — implementation handoff

Updated: 2026-10-27

## Purpose and current state

This project implements an independent PsychoPy experiment presenting a centrally flickering circular target. This document records the study-specific behavior, implementation boundaries, and validation requirements for maintenance or reuse. The stimulus implementation supports frame-indexed `square` and `sine` opacity modulation; the current `config.yaml` selects `square`.

Read `README.md`, `PSYCHOPY_DEVELOPMENT_CONTEXT.md`, and, when working on the existing NetStation integration, `NETSTATION.md`. They specify presentation, acquisition, diagnostics, and verification requirements. This handoff owns the study-specific choices; explicit choices here override older generic defaults in those guides.

The sibling `../ssvep-mapping-netstation/` is an implementation reference, particularly its display, keyboard, configuration, NetStation adapter, and package-contract components. Review before copying reusable components. Keep this project independent: do not import another experiment's package, modify shared acquisition infrastructure, copy recordings, or inherit its attention task or spatial mapping design.

## Confirmed user decisions

The original request contained conflicting sizes, shape descriptions, and diode positions. The user explicitly resolved these as follows:

- Target: white **circular disk, 3° diameter**. The target itself is not square; `square` refers only to its temporal opacity waveform.
- Fixation: opaque **red circular disk, 0.2° diameter**, drawn over the target.
- Background: **mid-gray**. Modulate a white target's opacity from 0 to 1, producing gray-to-white modulation, not black-to-white modulation.
- Waveform: **frame-indexed**, using configured refresh and reset to maximum opacity each trial. Both `square` and `sine` are supported; the current configuration uses a 15 Hz, 50% duty-cycle square wave.
- Diodes: **top-left onset**, **bottom-left offset**, not the originally mentioned two upper corners. Offset means the first frame with target and fixation removed.
- Viewing distance: **57.6 cm**.
- Blocks: **keypress before every block**, then 3 seconds blank; retain the 1-second ITI after every trial, including the last.

## Configuration and launcher

Load `config.yaml` relative to the experiment launcher, independent of the process working directory. The participant launcher exposes only `--participant` and `--mode`, plus standard help. Require both options. Participant is a string and must preserve leading zeros; safely encode it for output paths without changing the recorded identity. Mode choices are exactly `test` and `netstation`.

Use one presentation implementation in both modes. The only mode difference is acquisition: test mode must not import acquisition dependencies, open network connections, or attempt NetStation recording. Both modes retain local outputs and identical stimulus, timing, input, and semantic-event policies.

Configurable defaults:

| Group | Parameters and defaults |
| --- | --- |
| Display | Resolution 1920 × 1080 px; screen index 1 (zero-based secondary monitor); fullscreen true; synchronous flips |
| Calibration | Active width 58 cm; active height 33 cm; viewing distance 57.6 cm; expected refresh 60 Hz |
| Design | 1 block; 10 trials per block |
| Timing | Preparation 3.0 s; prestimulation 1.5 s; stimulation 10.0 s; ITI 1.0 s |
| Target | Center (0, 0); diameter 3.0°; white; frequency 15 Hz; waveform `square` (current) or `sine`; opacity range 0–1; initial phase at maximum |
| Fixation | Center (0, 0); diameter 0.2°; opaque red |
| Background | Mid-gray, normalized RGB (0.5, 0.5, 0.5) |
| Onset diode | Top-left; width/height 2.0° each; inset 0; white flash 0.1 s; otherwise black |
| Offset diode | Bottom-left; width/height 2.0° each; inset 0; white flash 0.1 s; otherwise black |
| NetStation | ECI IP 10.10.10.42; port 55513; NTP IP 10.10.10.51 |

Include window parameters, colors, sizes, durations, counts, frequency, opacity limits, and diode positions/insets in configuration. Validate types, finite values, bounds, and compatible timing before starting presentation/acquisition. Reject zero-frame positive phases, invalid counts, out-of-bounds geometry, and pulses longer than their containing stimulation/ITI phase; do not silently clamp parameters. No behavioral response task, randomization, EEG processing, or frequency sweep is requested.

## Exact sequence and drawing behavior

1. Complete startup checks and acquisition readiness, then show introductory instructions. Clear stale input once when entering the screen. Any fresh key begins, except Escape, which always aborts.
2. Show background alone for 3 seconds (diodes remain black).
3. Present fixation alone for 1.5 seconds.
4. Present the modulated target with constant fixation for 10 seconds. Draw fixation after the target on every frame so the target never covers it.
5. On the first removal flip, remove target and fixation together and start the offset diode pulse. The ITI lasts 1 second, including that pulse. No target or fixation appears during ITI.
6. Repeat steps 3–5 for all trials, including a full ITI after the final trial.
7. If more blocks remain, show a key-controlled break screen and repeat from step 2. Otherwise show a completion screen and allow a fresh key to dismiss it after recording cleanup.

The onset diode starts on the first target presentation flip. The offset diode starts on the first removal flip, not on the last displayed stimulation frame or a waveform extremum. Each pulse occurs once per trial; diode patches do not follow every modulation cycle. Patches stay black outside pulses, including instructions, preparation, prestimulation, and breaks. On abort, promptly clear target, fixation, and pulses.

Nominal default timed duration after the initial keypress is 128 seconds: 3 + 10 × (1.5 + 10 + 1). This excludes startup, operator screens, and cleanup.

## Spatial geometry and frame policy

- Use conventional central visual-angle sizing with the configured viewing distance. Convert angular extents to physical dimensions, then to pixels separately along each axis using the supplied active width/height and resolution. This preserves physically circular targets and physically square patches with the user's 58 × 33 cm measurements. Do not substitute the guide's older 53.5 × 30.1 cm dimensions or reject these supplied measurements through an inherited square-pixel tolerance.
- Angular patch sizes use the same central-size convention; edge anchoring is in framebuffer coordinates, not an eccentricity-dependent angular projection. Keep the full patch inside the window and record the resulting pixel bounds.
- Precompute opacity from frame index `n` and reset `n` to zero at each trial. For `square`, compute `phase = (n * frequency_hz / configured_refresh_hz) mod 1` and use maximum opacity when `phase < 0.5`, otherwise minimum opacity. For `sine`, use `min + (max-min) * 0.5 * (1 + cos(2π * frequency_hz * n / configured_refresh_hz))`.
- At 15 Hz/60 Hz with opacity limits 0–1, `square` repeats `1, 1, 0, 0`, while `sine` repeats `1, 0.5, 0, 0.5`. Against mid-gray, zero opacity reveals the background. These are sampled digital opacity values, not claims of physically calibrated luminance. Frequencies that do not divide the refresh rate evenly may yield unequal integer frame counts across nominal square-wave half-cycles.
- Convert durations with Python `round(seconds * configured_refresh_hz)` (ties to even). Default counts: 180 preparation, 90 prestimulation, 600 stimulation, 60 ITI, 6 pulse frames.
- A delayed frame stretches the sequence; do not advance phase by elapsed time, insert compensatory frames, or automatically repeat trials.
- Record first stimulation flip, first removal flip, actual frame intervals, and the final stimulation frame's held interval through removal. Distinguish nominal duration from observed elapsed duration.
- Use main-thread drawing, preloaded reusable visual objects, synchronous flips, and disabled automatic per-frame stimulus logging. No file I/O, printing, serialization, blocking networking, or sleeps in timed loops/callbacks.
- Use public PsychoPy `Window.timeOnFlip` for software timestamps and lightweight `callOnFlip` callbacks for acquisition capture/enqueue. Keep predicted, actual software, acquisition, and physical photodiode times distinct.
- Use the guide's keyboard adapter policy and poll Escape throughout startup, operator screens, timed phases, and completion. Ordinary keys during trials have no task meaning.

Startup display validation: verify configured versus public observed window size; perform 60 warmup flips followed by 120 measured frame intervals. Require finite positive intervals, SD ≤0.2 ms, no interval above 1.5 times the mean, measured refresh within 1% of configured refresh, and frequency strictly below half measured refresh. Save rejected measurements and fail explicitly; do not select another display or weaken thresholds automatically.

## Reuse with another EEG device

The stimulus geometry, waveform math, frame schedule, drawing order, photodiode behavior, local event meanings, and abort policy are acquisition-device independent and should remain unchanged when this protocol is moved to another EEG system. Keep one presentation path for simulated/test and hardware modes so changing the acquisition adapter cannot change visual timing or trial semantics.

The current `netstation` mode, ECI transport, NetStation clock conversion, ECI metadata constraints, network addresses, recording lifecycle, and `.mff` reconciliation are NetStation-specific. Do not carry those details into another device adapter by assumption. Replace them with the new device's connection, clock synchronization, trigger encoding, acknowledgement, recording, and cleanup requirements while preserving the semantic event boundaries below. Confirm whether the new device accepts event timestamps, generates timestamps on receipt, or requires a hardware trigger interface; record that distinction in the port's evidence.

The four-character event codes are the current wire representation, not the underlying protocol semantics. If the new device requires numeric triggers or different labels, define and save an explicit one-to-one mapping from each semantic event to its device code. Preserve global and within-block trial identity locally even if the hardware format cannot carry all metadata. Validate the new adapter with a fake transport, then verify real triggers and photodiode timing on the acquisition setup before collection.

## NetStation adapter and marker contract

This section describes the existing adapter only. It is a reference for lifecycle and evidence quality, not a transport specification for other EEG devices.

Follow the local `NETSTATION.md` in full for pinned dependency inspection, source hashes, API signatures, clock conversion, FIFO transport, errors, and lifecycle. Optional acquisition package: `egi-pynetstation==2.1.0`. The documented existing presentation environment is `psychopy2026` with Python 3.10.21 and PsychoPy 2026.1.3; inspect the actual environment rather than assuming shell Python matches it. Do not upgrade dependencies incidentally.

Use one serial transport worker, bounded FIFO capacity 4096, and bounded application waits of 15 seconds as documented. Prepare and validate event payloads outside timed presentation. Capture the package clock on the flip callback and convert in the worker; never send PsychoPy timestamps directly as EGI time or use worker-time `now` for visual events. Preserve the documented millisecond collision adjustment and all original times. Do not automatically retry unacknowledged sends.

Wire events:

| Code | Meaning | Boundary |
| --- | --- | --- |
| SESS | session_start | Recording startup succeeded; simulated equivalent in test mode |
| EXPR | experiment_start | First preparation flip after the initial intro keypress |
| BLST | block_start | First preparation flip of each block |
| TRST | trial_start | First prestimulation fixation flip |
| STON | stimulus_onset | First target flip, simultaneous with onset diode pulse |
| STOF | stimulus_offset | First target/fixation removal flip, simultaneous with offset diode pulse |
| BLEN | block_end | First break/completion screen flip after the final full ITI |
| SESE | session_end | Before recording stop; does not by itself mean successful protocol completion |

When EXPR and the first BLST share a flip, enqueue EXPR first. Maintain explicit four-character ASCII codes and metadata keys. Include RUID/MSEQ, PART, BLOC, TRIA, TWIN, and FREQ where applicable. Preserve a global trial identity and within-block identity. Rich local data need not be forced into flat ECI metadata.

Expected successful-run wire count is `3 + 2B + 3BT`, where B is blocks and T is trials per block: **35 events for the defaults**. Individual diode transitions and other diagnostic boundaries remain local-only and do not consume wire sequence numbers.

Start recording before the intro. Drain and stop after the final block/session-end events, before waiting for dismissal of the completion screen. Maintain recording through inter-block breaks. Acquisition failure must not silently switch to test mode.

On abort/failure, clear visual stimulation first, preserve incomplete trials, and independently attempt recording stop and disconnect. Do not fabricate scheduled offsets or block completion. Record actual abort removal locally, attempt session_end only while transport remains healthy, and preserve primary plus cleanup errors. Report uncertain remote recording state so the operator can check NetStation manually.

## Outputs and implementation boundaries

Create unique, non-overwritten run directories. Save source/resolved configuration, planned schedule, run/participant identity, environment and package provenance, display/calibration evidence, keyboard backend, trial summaries, frame intervals/quality flags, local events, and final/partial status. Checkpoint outside timed presentation and document potential losses on a hard crash.

Maintain the documented marker ledger, including simulated, acknowledged, not_sent, and unknown dispositions with clock and transport evidence. Test mode produces simulated ledger entries and a header-only acknowledged-marker CSV. In the existing integration, NetStation owns EEG recording and `.mff` files; this application does not acquire EEG samples. A port must document the corresponding ownership and output format for its EEG device.

Keep configuration, schedule/waveform math, presentation/input, acquisition, and output responsibilities separable and testable without creating a general experiment framework. A participant launcher named `experiment.py` and separate developer tooling are appropriate. Do not add developer controls to the participant CLI.

## Acceptance checks and handoff deliverables

1. Pure tests: configuration/type failures, CLI restrictions, leading-zero participant preservation, angular geometry/bounds, both square and sine waveform samples, the configured waveform selection, duration rounding, exact frame counts, block sequence, and final ITI.
2. Presentation tests with fakes: constant fixation layered above target, correct diode boundaries and six-frame pulses, no unintended target/fixation during ITI, fresh-key screen handling, Escape, partial runs, and identical mode schedules.
3. Acquisition tests with fake transport: marker mapping/count/order, metadata validation, FIFO order, capture/clock conversion, collisions, dependency mismatch, connection/synchronization/start/send failures, queue overflow, uncertain acknowledgments, and independent cleanup. Test mode must work with acquisition dependencies unavailable. Adapt these cases to the capabilities and failure modes of the selected EEG device.
4. Provide separate developer tools for offline validation/package inspection, monitor/display diagnostics, geometry preview, and a short presentation-only pilot. Offline checks must not open acquisition or execute/import hardware-active `test_connection.py`.
5. Run and record a real-window pilot on the intended screen when available, checking physical keys, geometry, completion, abort, and representative frame timing. Do not claim physical validation from mocks or inherited sibling results.
6. Before collection, separately verify physical diode placement/waveform/timing and real acquisition start/stop under presentation load. For the existing adapter, reconcile saved NetStation `.mff` event identity, order, metadata, and timestamps against local RUID/MSEQ evidence; for another EEG device, define and perform the equivalent reconciliation against its native recording.
7. Deliver launch/configuration documentation, a marker contract, project context, and a dated validation record identifying commands, actual versions, passed checks, failures, and outstanding physical/EEG validation.

Reference API documentation: https://psychopy.org/api/visual/window.html . The local engineering guides remain the detailed implementation contracts.
