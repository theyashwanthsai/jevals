"""If spacing calls out keeps them fast, the 1-2.5s tax is throttling on
OpenRouter's alpha endpoint, not Jev inference time."""
import time
from jev import decide

Q = {"x": {"type": "noul", "instructions": "Is this urgent?"}}
S = "Payouts failing for 3 days."

print("BURST (no gap):")
burst = []
for i in range(6):
    _, ms = decide(S, Q); burst.append(ms)
    print(f"  {i+1}  {ms:7.0f}ms")

print("\nSPACED (4s gap):")
spaced = []
for i in range(6):
    time.sleep(4)
    _, ms = decide(S, Q); spaced.append(ms)
    print(f"  {i+1}  {ms:7.0f}ms")

print(f"\nburst  mean {sum(burst)/len(burst):7.0f}ms")
print(f"spaced mean {sum(spaced)/len(spaced):7.0f}ms")
fast = sum(1 for x in spaced if x <= 500)
print(f"\nspaced calls within advertised 500ms: {fast}/6")
print("VERDICT:", "throttling on the OpenRouter path — model itself is fast"
      if sum(spaced)/len(spaced) < sum(burst)/len(burst) * 0.6
      else "not throttling — the latency is inherent")
