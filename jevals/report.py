"""Results, aggregation, reliability, regression comparison."""
import json, statistics
from collections import defaultdict
from pathlib import Path


class Report:
    def __init__(self, name, rubrics, client):
        self.name = name
        self.rubrics = {r.name: r for r in rubrics}
        self.client = client
        self.rows = []          # [(case, [Grade], meta)]
        self.errors = []
        self._finished = False

    # ------------------------------------------------------------ building
    def add(self, case, grades, meta):
        self.rows.append((case, grades, meta))

    def finish(self):
        self._finished = True
        return self

    # ------------------------------------------------------------ querying
    @property
    def grades(self):
        return [g for _, gs, _ in self.rows for g in gs]

    def by_rubric(self):
        out = defaultdict(list)
        for g in self.grades:
            out[g.rubric].append(g)
        return dict(out)

    @staticmethod
    def case_passed(grades):
        return all(g.passed for g in grades)

    @staticmethod
    def case_score(grades):
        """Weighted fraction of rubrics passed; 0 if any critical rubric failed."""
        if any(g.critical and not g.passed for g in grades):
            return 0.0
        total = sum(g.weight for g in grades) or 1.0
        return sum(g.weight for g in grades if g.passed) / total

    def summary(self):
        n = len(self.rows)
        passed = sum(1 for _, gs, _ in self.rows if self.case_passed(gs))
        gs = self.grades
        lat = self.client.latencies or [0]
        return {
            "suite": self.name,
            "cases": n,
            "errors": len(self.errors),
            "cases_passed": passed,
            "pass_rate": passed / n if n else 0.0,
            "mean_case_score": statistics.mean([self.case_score(g) for _, g, _ in self.rows]) if n else 0.0,
            "grades": len(gs),
            "borderline": sum(1 for g in gs if g.borderline),
            "escalated": sum(1 for g in gs if g.escalated),
            "mean_confidence": statistics.mean([g.confidence for g in gs]) if gs else 0.0,
            "calls": self.client.calls,
            "retries": self.client.retries,
            "input_tokens": self.client.input_tokens,
            "cost_usd": self.client.cost,
            "latency_p50_ms": statistics.median(lat),
            "latency_max_ms": max(lat),
            "rubrics": {
                name: {
                    "pass_rate": sum(1 for g in v if g.passed) / len(v),
                    "mean_confidence": statistics.mean([g.confidence for g in v]),
                    "borderline": sum(1 for g in v if g.borderline),
                }
                for name, v in self.by_rubric().items()
            },
        }

    # -------------------------------------------------------- reliability
    def reliability(self, bins=(0.0, 0.4, 0.6, 0.8, 0.95, 1.01)):
        """Is Jev's confidence trustworthy *on your data*?

        Needs Case.should_pass ground truth. Buckets grades by confidence and reports
        how often the grade was actually right in each bucket. A calibrated
        grader shows accuracy rising with confidence -- which is the only
        evidence that justifies picking an escalation threshold. Vendor
        calibration on vendor benchmarks does not transfer automatically.
        """
        pts = []
        for case, grades, _ in self.rows:
            for g in grades:
                if g.rubric in case.should_pass:
                    pts.append((g.confidence, g.passed == case.should_pass[g.rubric]))
        if not pts:
            return None
        out = []
        for lo, hi in zip(bins, bins[1:]):
            sel = [ok for c, ok in pts if lo <= c < hi]
            if sel:
                out.append({"range": f"{lo:.2f}-{min(hi, 1.0):.2f}", "n": len(sel),
                            "accuracy": sum(sel) / len(sel)})
        return {"points": len(pts), "accuracy": sum(ok for _, ok in pts) / len(pts),
                "buckets": out}

    # -------------------------------------------------------------- output
    def print(self, detail=True):
        s = self.summary()
        print(f"\n{'=' * 74}\n{self.name}\n{'=' * 74}")
        if detail:
            for case, grades, _ in sorted(self.rows, key=lambda r: r[0].id):
                mark = "PASS" if self.case_passed(grades) else "FAIL"
                print(f"\n  {mark}  {case.id}   score {self.case_score(grades):.2f}")
                for g in grades:
                    print(f"        {g}")
                    if g.note:
                        print(f"          -> {g.note}")
        print(f"\n{'-' * 74}")
        print(f"  cases       {s['cases_passed']}/{s['cases']} passed  "
              f"({s['pass_rate']:.0%})   mean score {s['mean_case_score']:.2f}")
        print(f"  grades      {s['grades']}   mean confidence {s['mean_confidence']:.2f}   "
              f"borderline {s['borderline']}   escalated {s['escalated']}")
        for name, r in s["rubrics"].items():
            print(f"    {name:<24} {r['pass_rate']:>6.0%} pass   conf {r['mean_confidence']:.2f}"
                  + (f"   {r['borderline']} borderline" if r["borderline"] else ""))
        if self.errors:
            print(f"  ERRORS      {len(self.errors)}")
            for cid, e in self.errors[:5]:
                print(f"    {cid}: {e[:120]}")
        rel = self.reliability()
        if rel:
            print(f"\n  RELIABILITY (grader accuracy vs your ground truth)")
            print(f"    overall {rel['accuracy']:.0%} on {rel['points']} labelled grades")
            for b in rel["buckets"]:
                bar = "#" * int(b["accuracy"] * 20)
                print(f"    conf {b['range']}  n={b['n']:<4} acc {b['accuracy']:>5.0%}  {bar}")
        print(f"\n  cost        ${s['cost_usd']:.6f} for {s['calls']} calls "
              f"({s['input_tokens']} tok, {s['retries']} retries)")
        print(f"  latency     p50 {s['latency_p50_ms']:.0f}ms   max {s['latency_max_ms']:.0f}ms")
        if s["cases"]:
            print(f"  per case    ${s['cost_usd'] / s['cases']:.8f}")

    def to_dict(self):
        return {
            "summary": self.summary(),
            "reliability": self.reliability(),
            "cases": [
                {"id": c.id, "passed": self.case_passed(gs), "score": self.case_score(gs),
                 "grades": [{"rubric": g.rubric, "value": g.value, "confidence": g.confidence,
                             "passed": g.passed, "borderline": g.borderline,
                             "escalated": g.escalated, "note": g.note} for g in gs]}
                for c, gs, _ in sorted(self.rows, key=lambda r: r[0].id)
            ],
        }

    def save(self, path):
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, default=str))
        return path

    def compare(self, baseline_path):
        """Diff against a saved run. Returns regressions/improvements per rubric+case."""
        base = json.loads(Path(baseline_path).read_text())
        old_cases = {c["id"]: c for c in base["cases"]}
        regressions, improvements = [], []
        for c, gs, _ in self.rows:
            old = old_cases.get(c.id)
            if not old:
                continue
            old_g = {g["rubric"]: g for g in old["grades"]}
            for g in gs:
                o = old_g.get(g.rubric)
                if not o:
                    continue
                if o["passed"] and not g.passed:
                    regressions.append((c.id, g.rubric, o["value"], g.value))
                elif not o["passed"] and g.passed:
                    improvements.append((c.id, g.rubric, o["value"], g.value))
        return {
            "baseline_pass_rate": base["summary"]["pass_rate"],
            "pass_rate": self.summary()["pass_rate"],
            "regressions": regressions,
            "improvements": improvements,
        }
