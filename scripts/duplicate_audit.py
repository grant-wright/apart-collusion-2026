"""Offline: how often duplicate task claims pay in Jira runs. NO API call is made.
Written in-sprint 24 Oct 2026.

Run from collusion_hackathon/colosseum with envs_ext on PYTHONPATH:
    $env:PYTHONPATH = "<repo>/envs_ext"; .venv/Scripts/python <repo>/scripts/duplicate_audit.py <repo>/runs/cap2 ...
Rebuilds each run's environment from run_config.json (same seed -> same instance; agent names are checked),
then for every task claimed by more than one agent reports the joint-score change from dropping each extra
claim. Under Apart's scoring an extra claim nets priority_bonus * weight - cost (bonus and penalty cancel).
"""
import json
import sys
import tempfile
import types
from pathlib import Path

from envs.dcops.jira_ticket.jira_ticket_env import JiraTicketEnvironment

import jira_multitask_env as m


def build(rc):
    cfg = {"environment": {**rc["environment_cfg"], "assignment_filling": False},
           "simulation": {"seed": rc["seed"], "max_iterations": 1},
           "communication_network": {"num_agents": rc["num_agents"], "topology": rc["topology"]},
           "llm": {"provider": "openrouter", "openrouter": {"model": "x"}},
           "experiment": {"output_dir": tempfile.mkdtemp()}}
    cls = m.JiraMultiTaskEnvironment if "max_tasks_per_agent" in rc["environment_cfg"] else JiraTicketEnvironment
    return cls(types.SimpleNamespace(), cfg, None)


def main():
    # --violation-penalty X re-prices the same claims under another penalty (then the logged-score check is skipped)
    args = sys.argv[1:]
    penalty = None
    if "--violation-penalty" in args:
        i = args.index("--violation-penalty")
        penalty = float(args[i + 1])
        del args[i:i + 2]
    total = paid = 0
    for root in args:
        for p in sorted(Path(root).rglob("run_config.json")):
            rc = json.loads(p.read_text(encoding="utf-8"))
            f = json.loads((p.parent / "final_summary.json").read_text(encoding="utf-8"))
            if f.get("status") != "complete":
                continue
            env = build(rc)
            assert sorted(env.agent_names) == sorted(f["assignment"]), (p, env.agent_names, list(f["assignment"]))
            acts = {a: m.claims_of(v) for a, v in f["assignment"].items()}
            score = lambda x: env._evaluate_assignment({a: (v or None) for a, v in x.items()} if isinstance(env, m.JiraMultiTaskEnvironment)
                                                       else {a: (v[0] if v else None) for a, v in x.items()})["score"]
            base = score(acts)
            assert abs(base - f["joint_reward"]) < 1e-6, (p, base, f["joint_reward"])
            if penalty is not None:
                env.violation_penalty = penalty
                base = score(acts)
            claimants = {}
            for a, ts in acts.items():
                for t in ts:
                    claimants.setdefault(t, []).append(a)
            for t, agents in claimants.items():
                for extra in agents[1:]:
                    without = {a: [x for x in ts if not (a == extra and x == t)] for a, ts in acts.items()}
                    gain = base - score(without)
                    total += 1
                    paid += gain > 0
                    print(f"{rc['sweep']:3} seed {rc['seed']:3} {t:24} extra claim by {extra:11} joint {gain:+6.1f}")
    print(f"\nduplicate extra claims: {total}; joint score higher with the duplicate: {paid}")


if __name__ == "__main__":
    main()
