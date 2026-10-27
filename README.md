# Central SSVEP response validation

This independent PsychoPy experiment presents a white circular target (3° diameter) at the center of a mid-gray display. Its opacity follows a configurable, frame-indexed sine or square wave while an opaque red fixation disk (0.2° diameter) remains above it. The current configuration uses a 15 Hz square wave with a 50% duty cycle. A top-left diode patch marks target onset and a bottom-left patch marks the first target-removal frame.

## Environment and launch

Use the existing reviewed environment from the project directory:

```bash
conda run -n psychopy2026 python experiment.py --participant 001 --mode test
conda run -n psychopy2026 python experiment.py --participant 001 --mode netstation
```

`--participant` preserves its string identity, including leading zeros. `test` and `netstation` use the same presentation path. Test mode does not import `egi_pynetstation`, open network connections, or control recording. Escape aborts at all screens and phases.

The launcher always loads `config.yaml` beside `experiment.py`, regardless of the process working directory. Run folders are allocated under `data/results/<participant>/runNNN` without overwriting earlier evidence.

Before using `netstation` mode, enable the ECI listener in NetStation and prepare the acquisition session. This application starts and stops recording but does not acquire EEG samples or create `.mff` files itself.

## Developer checks

These commands do not contact NetStation:

```bash
conda run -n psychopy2026 python tools.py validate
conda run -n psychopy2026 python tools.py inspect-netstation
conda run -n psychopy2026 python tools.py check-display
conda run -n psychopy2026 python tools.py preview-geometry
conda run -n psychopy2026 python tools.py pilot --participant SOFTWARE_PILOT
conda run -n psychopy2026 python -m unittest discover -s tests -v
```

`check-display`, `preview-geometry`, and `pilot` open the configured display. They must be run in the local graphical session with the intended monitor attached. The developer pilot uses one shortened trial while preserving the configured display, geometry, flicker, input, diode, and acquisition-independent policies. These controls are deliberately absent from the participant launcher.

## Frame policy and evidence

Durations are converted with Python `round(seconds * configured_refresh_hz)`. Each trial resets the target to maximum opacity. The `target.waveform` setting accepts `square` or `sine`.

For `square`, the target uses a 50% duty cycle:

```text
phase[n] = (n * frequency_hz / configured_refresh_hz) mod 1
opacity[n] = max, if phase[n] < 0.5; otherwise min
```

With the configured 15 Hz frequency, 60 Hz refresh rate, and opacity range 0–1, the frame sequence repeats `1, 1, 0, 0`: two frames of the white target followed by two frames at zero opacity, where the mid-gray background is visible. The square wave is sampled by display frames, so other frequency/refresh combinations may not produce equal integer counts of high and low frames in every cycle.

For `sine`, opacity follows a cosine-phase sinusoid that begins at its maximum:

```text
opacity[n] = min + (max-min) * 0.5 * (1 + cos(2π * frequency_hz * n / configured_refresh_hz))
```

At 15 Hz and 60 Hz with an opacity range of 0–1, the sine sequence repeats `1, 0.5, 0, 0.5`. In both modes, opacity modulates a white target over the mid-gray background; it does not imply physically calibrated luminance.

Delayed frames stretch the sequence; phase is not advanced or repaired. Startup performs 60 warmup flips and measures 120 intervals. It rejects nonpositive intervals, SD above 0.2 ms, an interval above 1.5 times the mean, refresh error above 1%, and frequency at or above half the measured refresh.

Run evidence includes source/resolved configuration, planned schedule, environment, display calibration and refresh evidence, per-frame software times, trials, local events, all intended marker dispositions, acknowledged markers, and acquisition lifecycle evidence. PsychoPy flip times, EGI converted times, and physical photodiode times are distinct. Physical diode and EEG timing still require measurement on the collection setup.
# ssvep-response-verification-netstation
