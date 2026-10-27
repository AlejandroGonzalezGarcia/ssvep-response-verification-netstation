# Marker contract

Only the following semantic boundaries are sent. All codes are fixed four-character ASCII values. `RUID` and monotonically increasing `MSEQ` identify the run and intended wire order. Applicable markers also include `PART`, `BLOC`, `TRIA`, `TWIN`, and `FREQ`.

| Code | Event | Boundary |
| --- | --- | --- |
| SESS | session_start | Recording startup succeeded, or the simulated equivalent |
| EXPR | experiment_start | First preparation flip after the introductory key |
| BLST | block_start | First preparation flip of each block |
| TRST | trial_start | First prestimulation fixation flip |
| STON | stimulus_onset | First target flip and onset-diode pulse |
| STOF | stimulus_offset | First target/fixation removal flip and offset-diode pulse |
| BLEN | block_end | First break/completion screen flip after the final full ITI |
| SESE | session_end | Before recording stop; it does not assert protocol completion |

When `EXPR` and the first `BLST` share a flip, `EXPR` is queued first. For `B` blocks and `T` trials per block, a successful run has `3 + 2B + 3BT` wire events (35 with the default configuration). Diode pulse endings and diagnostic boundaries are local evidence and consume no `MSEQ`.

Test mode records simulated dispositions in `markers.json` and writes a header-only `markers.csv`. NetStation mode places all ECI work on one bounded FIFO worker. Lack of a positive acknowledgment is recorded as uncertain and is never automatically retried.
