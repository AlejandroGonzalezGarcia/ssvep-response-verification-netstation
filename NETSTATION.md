# Reusable NetStation integration context

Updated: 2026-10-22. Canonical location: `eeg-projects/NETSTATION.md`.
Copy this file and `PSYCHOPY_DEVELOPMENT_CONTEXT.md` together into a new project.
This is the acquisition engineering contract for a new PsychoPy simulation on the
lab station. The companion file defines presentation and display defaults. Neither
file requires importing another experiment or the lab's shared acquisition runtime.

This revision supersedes the 2026-09-30 guidance based on the old local 1.0.x
checkout. It reflects static inspection of `ssvep-mapping-netstation/config.yaml`,
`mapping/netstation.py`, `mapping/egi_contract.py`, `mapping/markers.py`,
`MARKERS.md`, `README.md`, and `VALIDATION.md`. Those are implementation references
in the originating repository, not dependencies required to read this handoff.

## Transfer contract

Build the simulation around one presentation path. Selecting `test` or `netstation`
changes acquisition only: preserve stimuli, schedule/RNG, frame policy, input,
scoring, semantic events and local behavioral outputs. Test mode must work without
acquisition imports, network activity or recording. Never silently fall back to it.

PsychoPy owns presentation, responses and local evidence. NetStation owns EEG
recording and acquisition-side files. `egi-pynetstation` sends ECI commands and
markers; it does not return EEG samples, configure montages/sampling rates, create
participant records, or replace response/scanner/eye-tracker inputs. Inventory any
such functions separately when porting an existing experiment.

These two files specify reusable engineering decisions, not an executable framework.
A new repository still needs its own adapter, launcher, configuration and checks
(or a deliberately vendored, reviewed implementation). Do not claim acquisition
readiness merely because it follows these documents.

## Default station configuration

Use these defaults for the same lab station; do not ask for them again:

```yaml
netstation:
  netstation_ip: 10.10.10.42
  port: 55513
  ntp_ip: 10.10.10.51
```

The ECI TCP listener and NTP service are separate endpoints. Prepare the acquisition
session and enable the ECI listener in NetStation before collection. NTP normally
uses UDP 123. Validate IPv4 addresses and integer port range 1–65535 (reject booleans)
before opening sockets. For a different station, supply its actual configuration.
Do not infer the stimulus computer's address, subnet, amplifier model, NetStation
version or sampling rate. Do not change routes/firewalls automatically.

## Dependency and compatibility contract

Optional acquisition dependency: `egi-pynetstation==2.1.0` in the interpreter that
runs PsychoPy. This project does not require a sibling package checkout or external
`ntplib`. Do not copy old 1.0.x synchronization recipes or install an unspecified
latest package. The current presentation reference uses Python 3.10.21 and PsychoPy
2026.1.3 in `psychopy2026`; see the companion guide for the complete reference stack.

Use `from egi_pynetstation.NetStation import NetStation`. Before graphics or network
operations, inspect the installed distribution version, actual imported module paths,
source hashes and required API signatures. Reject mismatches explicitly; do not
replace expected hashes merely to bypass a failure. An intentional version change
requires source review and renewed tests. Reviewed wheel SHA256:
`354a852fe528151453d1273c09bf1357a46269e8d4f369d9f09f8dd48075dae4`.

Reviewed source SHA256 values:

| Module | SHA256 |
| --- | --- |
| NetStation.py | 1e64ef41544db4a45deebffabe3b1e85f2dd61048534c173875da19d593568f8 |
| __init__.py | 6b65ddb0104dbb0d031f5251f5e7944c1939502b7668767f44958d611226d7fa |
| eci.py | 32da0eea162020bffe6bb895951fd7ecfc60cbcb7e1fa76562f7cc7ae69fcea3 |
| egi_ntp.py | e3944da98b5cc47a370921f96d8f54e443b643ce37ea7068006ca21d4075af07 |
| exceptions.py | ac61fb519e3a47f5f1b0a3c62e40f9bbfc65c4ee0a78891e7387821d184dab3a |
| socket_wrapper.py | 3c9179e4e3b06e5dc2e77a575ef4a799b025e696d6bd6cb12fcba4581f246170 |
| util.py | a6813a29a49f10162320a066374cc1405b6a92752196fa1e02a10968a705a676 |

Verify these APIs without constructing a connection: `connect(ntp_ip=..., strict_eci=True)`,
`begin_rec()`, `capture_time()`, `time_at_capture(captured_time=...)`,
`send_event(start=..., duration=..., event_type=..., label=..., desc=..., data=..., wait=True)`,
`clock_state()`, `session_summary()`, `event_errors()`, `eci_errors()`, `end_rec()`,
and `disconnect()`. Imported package modules must come from the same installation.

## Define the marker contract before coding trials

Inventory the new study's semantic events, exact emission boundary, clock basis,
condition/trial identity and analysis needs. Map each transmitted event explicitly
to a unique four-character ASCII code. Never truncate names, use randomized hashes,
or collapse distinct events implicitly. Unknown events and mapping collisions fail
before acquisition. Electrical TTL resets need no ECI event unless they have an
independent scientific meaning. Keep local diagnostic boundaries explicitly separate.

The reference study transmits these 11 codes; reuse meanings where applicable, but
adapt the inventory to the new protocol rather than imposing SSVEP tasks or counts:

| Code | Semantic event | Reference emission boundary |
| --- | --- | --- |
| SESS | session_start | Recording startup succeeded |
| EXPR | experiment_start | Instructions complete; execution begins |
| BLST | block_start | First pre-block gray flip |
| TRST | trial_start | First prestimulus flip |
| STON | stimulus_onset | First stimulation flip |
| TKON | task_start | Fixation changes red to green |
| RESP | button_press | Eligible configured response-key event |
| TKOF | task_end | Fixation changes green to red |
| STOF | stimulus_offset | Scheduled removal flip; ITI or final post-block begins |
| BLEN | block_end | Message flip after post-block gray |
| SESE | session_end | Before recording stop; does not imply protocol completion |

The reference keeps FXON, FXOF, TREN, EXPE, PDTS, PDTE, PDBS and PDBE local-only,
without wire sequence IDs. Its final BLEN defines successful completion. Its
257 + R wire count belongs to its two-block/50-trial protocol only. A new protocol
must state its own expected counts and completion/abort semantics.

Metadata is a flat dictionary with four-character ASCII keys. Use built-in `bool`,
`int`, finite `float` or ASCII `str`; convert NumPy scalars deliberately. Integers
must fit signed 32 bits. Strings must fit 65535 bytes, metadata count at most 255,
and the entire serialized packet must fit the 16-bit length limit. Validate total
size conservatively including headers, label, description, keys and values. Do not
serialize nested objects as if they were supported scalar wire values. Keep full
rich payloads locally. Validate prepared payloads including the eventual MSEQ field.

Reference metadata:

| Keys | Meaning |
| --- | --- |
| RUID, MSEQ | Run UUID and monotonically increasing intended wire-event sequence |
| PART, SESS | Participant string (preserve leading zeros) and session identity |
| TRIA, BLOC, TWIN | Global trial, block and within-block trial |
| COND | Condition identity |
| FREQ, XDEG, YDEG, ECCE, SECT | Reference study's frequency and spatial parameters |
| RTIM, RESP, RSLT, KEYN | Reaction time, original response time, result and key |

RUID/MSEQ connect local evidence to saved .mff events. Only intended wire events
consume MSEQ. Preserve full input time and scoring locally; a response's ECI time
is detection/processing time, not backdated physical key-down. The reference accepts
response-key input from EXPR through final BLEN inclusively, including ITI/break
presses, and drains buffered eligible responses after BLEN. This eligibility rule
is study-specific; define it explicitly in a new simulation.

## Transport, clock conversion and lifecycle

Keep drawing/flips on the main thread. Use one serial ECI worker with bounded FIFO,
capacity 4096 and bounded application operation waits of 15 seconds as reference
defaults. Queue overflow or worker failure stops acquisition explicitly. The timeout
bounds the adapter wait, not a promise that a blocked library call has terminated.
No concurrent socket transactions, thread per event, or blocking network calls in
flip callbacks. Prepare/validate payloads before timed presentation.

Worker lifecycle: construct `NetStation(ip, port)` →
`connect(ntp_ip=ntp_ip, strict_eci=True)` → `begin_rec()` → inspect diagnostics →
process events/checkpoints → drain healthy accepted events → `end_rec()` →
inspect diagnostics → `disconnect()`. Track partial connection/start attempts and
unknown remote state. Attempt stop after an attempted start, and attempt disconnect
independently even when stop/diagnostics fail. Version-specific private socket cleanup
must remain isolated and reviewed, never scattered through trial code.

For a visual event, register `Window.timeOnFlip` and a lightweight `callOnFlip`
callback. Preserve the original PsychoPy flip timestamp; capture the package clock
with `capture_time()` in the callback and enqueue the prepared event without waiting.
The worker converts captured time using `time_at_capture()`. Do not pass PsychoPy,
Unix, LSL or RT timestamps directly as `start`, and do not substitute worker-time
`start="now"`. Retain default background drift correction. Checkpoints drain and
inspect diagnostics without `resync()`; do not reset the epoch between queued events.

Keep three separate timing layers: original PsychoPy/input time, natural converted
EGI time, and transmitted EGI time. The reference collision policy is:

```python
natural_ms = int(natural_start_s * 1000)
transmitted_ms = max(natural_ms, previous_transmitted_ms + 1)
adjustment_ms = transmitted_ms - natural_ms
start = transmitted_ms / 1000
# If float rounding would truncate one millisecond early:
if int(start * 1000) != transmitted_ms:
    start = math.nextafter(start, math.inf)
assert int(start * 1000) == transmitted_ms
```

Require finite nonnegative natural time and transmitted milliseconds in
0..2147483647. Keep the prior wire millisecond across the recording, initialized
below zero. Send a built-in float `start` in seconds, `duration=0.001`,
`event_type=code`, `label=code`, `desc=semantic_event`, `data=metadata`, `wait=True`.
Require a positive acknowledgment (`response is True`). The 1 ms duration is packet
metadata, not stimulus duration. Preserve original clocks unchanged and log natural
and transmitted milliseconds, adjustment count and maximum adjustment. NATM/ADJM
are local evidence in the reference, not wire metadata. No frame insertion, sleep,
automatic resend or clock reset is used to resolve collisions.

## Evidence, errors and shutdown

Maintain one ledger row per intended marker with identity/payload, original flip/input
and capture times/clock basis, natural and transmitted EGI times, queue/send/response
times, final disposition and errors. Distinguish `acknowledged`, `not_sent`, `unknown`
and `simulated`. Reference `markers.csv` contains acknowledged events only;
`markers.json` includes every intended wire event, failed sends and lifecycle evidence.
Test mode produces simulated JSON rows and a header-only acknowledged CSV. Local-only
boundaries are separate. Do not invent timestamps for unattempted sends or responses.

No acknowledgment is not proof of non-delivery: do not retry automatically. At bounded
shutdown mark unresolved in-flight sends unknown and unattempted queued sends not_sent.
Late acknowledgments can add evidence but must not relabel shutdown-unknown events as
successful. ECI acknowledgment does not prove inclusion or correct timing in .mff.

On abort, remove the visual stimulus promptly, retain incomplete trials and partial
output, and attempt independent cleanup. Do not fabricate scheduled onset/offset/task
or block completion events. Attempt session_end only while transport remains healthy.
Report unknown recording state and instruct the operator to check/stop NetStation
manually if stopping was not confirmed.

Errors must name NetStation, operation, ECI/NTP endpoints, event/code/trial when
applicable, original exception type/message (including `.message` when useful), known
state and actionable checks. Preserve primary failures alongside cleanup failures.
Distinguish TCP, handshake, NTP, recording and marker failures without guessing causes.

## Acceptance and handoff

Provide configuration validation, offline package/API inspection, test mode, display
check, geometry preview and a short pilot. Offline checks must not open acquisition.
Never import the historical `test_connection.py` for inspection/discovery: it contains
hardware-active top-level code. Do not run hardware connection tests during document
review or broad test discovery.

Verify marker mapping/serialization, timestamp conversion/collisions and FIFO ordering
with fake transport. Exercise missing/incompatible package, invalid configuration,
connection/NTP/start failure, queue overflow, send rejection, disconnect, Escape,
partial startup and uncertain cleanup. Compare test/acquisition presentation policy,
RNG outcomes, schedules and scoring; wall-clock values need not be equal across runs.

Before participant collection, verify real recording start/stop and representative
frame timing under acquisition load. Reconcile saved .mff events with RUID/MSEQ,
codes, metadata, order and transmitted timestamps. Measure physical visual/response
alignment and any photodiode/DIN pulses. Record actual amplifier, NetStation version,
OS, interpreter/package provenance and station profile with the evidence.

The reference has software/fake-transport checks and real-window display pilots;
physical DIN/EEG timing and saved-.mff acceptance remain unverified in its documented
validation. Its top→DIN1/start and bottom→DIN2/stop white pulses (2 cm, 0.1 s) are an
optional study design, not an ECI requirement. No hardware was contacted for this
2026-10-22 documentation update. Do not carry old pass counts forward as new evidence.
