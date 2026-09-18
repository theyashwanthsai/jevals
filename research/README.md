# research

The probe suite used to work out what Jev can and cannot do, before `jevals`
was designed around it. Not part of the library - kept because the design
decisions in `jevals/` cite these measurements.

Results and conclusions: [`../FINDINGS.md`](../FINDINGS.md)

| file | what |
|---|---|
| `smoke.sh` | one raw curl; verifies endpoint, auth and body shape |
| `run.py` | runner for `cases.py`, with auto-checks for falsifiable properties |
| `cases.py` | 13 probes: 5 on advertised claims, 8 targeting documented failure modes |
| `latency_probe.py` | 20 identical calls; shows the burst latency is quantized queueing |
| `rate_probe.py` | burst vs spaced, isolating throttling from inference time |
| `jev.py` | the throwaway client these predate `jevals/client.py` |

```bash
python3 research/run.py --group claims
python3 research/run.py --group stress
```
