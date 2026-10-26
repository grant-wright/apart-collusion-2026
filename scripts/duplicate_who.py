# For every duplicated Jira task: claimants, colluder flags, arm. Offline, reads final_summary + run_config only.
import json, sys
from pathlib import Path
from collections import Counter
tally = Counter()
for root in sys.argv[1:]:
    for p in sorted(Path(root).rglob("run_config.json")):
        rc = json.loads(p.read_text(encoding="utf-8"))
        f = json.loads((p.parent / "final_summary.json").read_text(encoding="utf-8"))
        if f.get("status") != "complete": continue
        col = set(rc["colluders"])
        claims = {}
        for a, v in f["assignment"].items():
            ts = v if isinstance(v, list) else ([v] if v else [])
            for t in ts:
                if t and t != "skip": claims.setdefault(t, []).append(a)
        for t, ag in claims.items():
            if len(ag) < 2: continue
            nc = sum(a in col for a in ag)
            kind = "both colluders" if nc == len(ag) else ("colluder+innocent" if nc else "innocents only")
            tally[(rc["sweep"], kind)] += 1
for (arm, kind), n in sorted(tally.items()): print(f"{arm}: {kind}: {n}")
