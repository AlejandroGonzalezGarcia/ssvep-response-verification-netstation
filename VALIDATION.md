# Validation record

Date: 2026-10-22

Software validation is recorded below when the implementation checks are run. Real-window, physical-key, photodiode, and NetStation/`.mff` acceptance require the intended local graphical session and acquisition hardware and are not claimed by unit tests.

## Completed software checks

Run on 2026-10-22 with `/opt/anaconda3/envs/psychopy2026/bin/python`:

- Python 3.10.21; PsychoPy 2026.1.3; pyglet 1.5.27; NumPy 2.2.6; Pillow 10.4.0; PyYAML 6.0.2; egi-pynetstation 2.1.0.
- `python -m unittest discover -s tests -v`: 42 tests passed.
- `python tools.py validate`: passed with 10 trials and frame counts 180 preparation, 90 prestimulation, 600 stimulation, 60 ITI, and six frames for each diode pulse.
- `python tools.py inspect-netstation`: passed. The installed version, import root, all seven documented SHA256 values, and all required public API signatures matched the pinned contract. No connection was opened.
- `python -m py_compile experiment.py tools.py response_validation/*.py tests/*.py`: passed.

The unit suite covers strict configuration and CLI failures, leading-zero identity, calibrated geometry, waveform samples and reset, exact frames and final ITI, refresh acceptance/rejection, draw layering, pulse boundaries, absence of target/fixation during ITI, 35-event mapping/order, simulated disposition, FIFO sends, millisecond collision adjustment, positive acknowledgment, and independent lifecycle cleanup. Tests use fakes and do not constitute display or EEG validation.

Required pre-collection checks:

1. Run `tools.py check-display` and `tools.py preview-geometry` on screen index 1; verify active dimensions, placement, physical size, refresh, and keys.
2. Run `tools.py pilot`, exercise completion and Escape, and inspect output evidence and frame intervals.
3. Measure the target and both diode signals physically, including onset/removal alignment and waveform.
4. In `netstation` mode, verify start/stop under presentation load and reconcile `.mff` codes, order, `RUID`, `MSEQ`, metadata, and times against local evidence.

The repository does not weaken a failed display check, change screens automatically, contact hardware from offline tools, or claim that ECI acknowledgment proves inclusion in `.mff`.
