# Continuous physical synchronization — 2026-10-25

The loaded elbow tracks Gym substantially more closely with bounded feedback correction. The identical continuous trajectory reduced elbow RMS error from **2.874° to 0.581° (79.8%)**, peak error from **4.320° to 1.563°**, and ended at **0.033°** error. A separate, larger 117-second six-axis run passed and ended with elbow error **−0.104°**. These are encoder-to-request comparisons, not independent optical measurements or a guarantee of 100% geometric agreement.

## What changed

- Kept the verified device-specific zero/direction mapping unchanged. The earlier ~3.4° elbow discrepancy varied with load and movement; offsetting calibration would conceal that tracking error.
- Added a bounded outer proportional/integral controller. Command speed is limited to 0.3 rad/s and acceleration to 1.2 rad/s². Bias, correction, integration rate and stale cycles are bounded. Raw/model limits, whole-arm collision checks, tracking/jump guards, exclusive ownership and controller lease remain active.
- Normal Stop and re-enable preserve validated learned load compensation in memory, preventing a new gravity sag each time. Faults, failed holds and reconnection discard it. No EEPROM or motor gain changes; no torque-off writes.
- One checked feedback frame replaces four scalar register reads per motor. In a 1,350-cycle read-only comparison, six-motor read time averaged 7.34 ms before and 3.77 ms after. This measures serial reads, not total end-to-end UI latency.
- HTTP and MCP now expose requested, measured and compensated command angles separately. The Connection UI shows per-joint differences and largest error during Gym → Real arm, plus a temperature-confirmation count.

## Physical comparison

All six STS3215 motors were connected. The robot moved without payload in the cleared workspace. Every target segment passed offline MuJoCo collision checks before motion; runtime guards remained active. The target was sent through the actual Gym session command API, with the connection service controlling the physical arm. This was not a synthetic servo test.

The 46-second profile uses a 5-second transition, 36 seconds of synchronized 12-second-period motion, then a 5-second stationary hold. Center and amplitudes are in [summary.json](continuous-sync-2026-10-25/summary.json). Both runs use the same center, amplitude and wave timing; startup positions and accumulated load compensation can differ. RMS/peak measurements below use t=7…41 seconds, excluding the initial transition and final hold.

| Joint | Before RMS ° | After RMS ° | Before peak ° | After peak ° | After final signed error ° |
| --- | ---: | ---: | ---: | ---: | ---: |
| Shoulder pan | 1.332 | 0.671 | 2.118 | 1.682 | +0.264 |
| Shoulder lift | 1.364 | 0.583 | 2.500 | 1.466 | −0.176 |
| Elbow flex | 2.874 | 0.581 | 4.320 | 1.563 | +0.033 |
| Wrist flex | 1.390 | 0.579 | 2.162 | 1.421 | 0.000 |
| Wrist roll | 1.463 | 0.728 | 2.146 | 1.730 | 0.000 |
| Gripper | 1.357 | 0.613 | 2.098 | 1.455 | −0.125 |

Final means the last recorded sample, not a confidence bound. Requested targets and returned telemetry are sampled asynchronously through HTTP; the error includes tracking delay. CSV fields preserve commanded and measured angles in radians. RMS = sqrt(mean((actual − desired)²)); degree conversion is 180/π. No time shifting or smoothing is applied to the reported errors.

Raw traces: [baseline](continuous-sync-2026-10-25/baseline.csv), [final build](continuous-sync-2026-10-25/final-comparison.csv). There were 542 and 523 samples respectively. Maximum observed feedback age in the final comparison was 63.1 ms; mean target-request duration was 17.4 ms and maximum 100.5 ms. HTTP timing is not a hard realtime guarantee.

## Larger continuous test and restart behavior

The 117-second run transitions for 6 seconds, moves all six axes for 96 seconds with independent 13–19 second periods and phase offsets, and holds for 15 seconds. Amplitudes range from 0.10 to 0.28 rad (5.7–16.0°); pan and wrist roll sweep approximately 32° peak-to-peak. All 1,171 preflight segments passed. The live test recorded 1,355 samples without a motion fault; max observed feedback age was 78.9 ms.

| Joint | Moving RMS °, t=10…98 s | Moving peak ° | Final signed error ° |
| --- | ---: | ---: | ---: |
| Shoulder pan | 0.937 | 2.102 | −0.044 |
| Shoulder lift | 0.578 | 1.853 | −0.107 |
| Elbow flex | 0.548 | 1.371 | −0.104 |
| Wrist flex | 0.471 | 1.311 | +0.059 |
| Wrist roll | 0.945 | 2.034 | −0.077 |
| Gripper | 0.544 | 1.374 | −0.138 |

[Endurance trace](continuous-sync-2026-10-25/endurance-confirmed.csv). Seven isolated temperature jumps required confirmation; each had three subsequent agreeing readings. For example, motor 5 returned [62, 36, 36, 36]°C. Confirmation events and times are in summary.json.

A follow-up test held stopped for 3 seconds, enabled at the current pose for 4 seconds, then synchronized to the aligned stationary Gym target for 8 seconds. No encoder position change was observed in any phase; torque stayed on. [Restart trace](continuous-sync-2026-10-25/hold-restart.json). This tests restarting in the same connection, not compensation persistence across program restart.

UI checks verified the new fields, disabled jog controls while syncing and successful Stop & hold. A stationary UI reading of 0.00° after explicitly matching Gym to measured pose is only a display/hold check; it is not the accuracy experiment above. All 14 existing scene sessions were preserved. The arm was left with streaming off and torque on.

## Failed trials and diagnosis

Failures were retained during development rather than counted as successful motion:

- An early baseline setup stopped on approximately 1.67 mm simulated gripper/table overlap after the loaded elbow sagged when the hold goal was reset to its encoder reading. The arm was raised slowly to a preflighted clear pose. No collision exclusion was added.
- The first feedback-gain trial stopped after about 31 seconds on the test harness's 55°C limit; adjacent gripper readings were 37°C. A repeat passed, and the bounded gains were subsequently adjusted using measured tracking results.
- A larger run with scalar reads stopped around 49 seconds on unsafe telemetry. The old error message did not identify the offending value; that reporting gap was fixed.
- A block-read run stopped around 33 seconds on motor 1 reporting 78°C, surrounded by 36°C readings. Switching to coherent frames reduced latency but did not eliminate the anomalous temperatures.
- An initial confirmation scheme stopped around 90 seconds on [77, 36, 48]°C because the confirmation readings disagreed. The final bounded scheme requires three readings within 3°C among at most five frames; any two readings ≥65°C always fault. Transport, device and voltage errors fail immediately. No commands are written during confirmation and faults never auto-resume.

The source of sporadic temperature anomalies remains unconfirmed. They are exposed diagnostically, not claimed to be a repaired sensor. Consistent high temperatures still fault at the existing 65°C threshold. Persistent or worsening anomalies require hardware/firmware diagnosis.

## Automated checks and review

- 61 focused backend tests passed: tracking controller, driver frame/temperature validation, connection service, module integration and MCP.
- 21 frontend tests passed; TypeScript and production build passed. The existing large Three.js chunk warning remains.
- Fatal Python lint checks and whitespace checks passed.
- Independent review identified failed-stop compensation retention, stale compensated holds, and SDK raw-response length validation. Each received a regression test and fix. Final temperature-confirmation review found no important regression.
- The entire unrelated manipulation-policy regression suite was not rerun for this connection-layer change.

## Accuracy limits

Encoder resolution is 360/4096 = 0.08789° per tick. A fractional target can show a smaller numerical error than one tick; this does not imply sub-tick physical measurement precision. Backlash, compliance, assembly offsets, gear behavior and payload remain outside this encoder-only validation. Available camera framing did not independently establish absolute link angles. Higher speed, new payloads and other workspace regions were not characterized by these runs. Physical acceleration and jerk were not independently measured; software command bounds and successful multi-axis trials support smoother command behavior, not a certified mechanical motion bound.

The achieved result is lower measured tracking error with smooth bounded commands and working restart behavior. Exact 100% physical correspondence is not established.
