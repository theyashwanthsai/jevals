"""Is the 70-500ms claim broken by the model, or by OpenRouter's alpha proxy?
20 identical minimal calls. If latencies cluster at ~1s intervals it's polling
overhead in the proxy, not inference time."""
import statistics
from jev import decide

Q = {"x": {"type": "noul", "instructions": "Is this urgent?"}}
S = "Payouts failing for 3 days."

lat = []
for i in range(20):
    _, ms = decide(S, Q)
    lat.append(ms)
    print(f"  {i+1:2d}  {ms:7.0f}ms")

print(f"\nsorted: {' '.join(f'{x:.0f}' for x in sorted(lat))}")
print(f"p50 {statistics.median(lat):.0f}ms  min {min(lat):.0f}  max {max(lat):.0f}")
print("\nhistogram (500ms buckets):")
for b in range(0, int(max(lat)) + 500, 500):
    n = sum(1 for x in lat if b <= x < b + 500)
    if n:
        print(f"  {b:5d}-{b+500:5d}ms  {'#' * n} ({n})")
print(f"\nwithin advertised 500ms: {sum(1 for x in lat if x <= 500)}/20")
