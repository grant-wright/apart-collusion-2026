"""Offline: one row per Colosseum run, plus per-(model, condition) means. NO API call is made.
Written in-sprint 24 Oct 2026.

    python scripts/summarise_runs.py runs/pilot2 [--csv out.csv]

Runs Apart's optimum solver (compute_jira_optimal.py --write-json) for any run lacking
optimal_summary.json, then reports coalition advantage, joint score vs optimum, violations, colluder
posts on the secret vs other boards, turn order, calls and token-priced cost (rates below).
"""
import argparse
import csv
import json
import statistics
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COLOSSEUM = REPO / "collusion_hackathon" / "colosseum"
RATES = {"qwen/qwen-2.5-7b-instruct": (0.10, 0.20), "meta-llama/llama-3.3-70b-instruct": (0.10, 0.32)}


def regrets(rc, m, f, which):
    """(coalition mean, non-coalition mean) regret. 'multi' = JiraMultiTaskEnvironment's regret_multi (subsets
    up to the cap); 'apart' = Apart's metrics.py regret (one task or skip); 'auto' = multi where the env wrote
    it, else Apart's -- except on cap>1 runs that predate regret_multi, where Apart's undercounts (None)."""
    # Off Jira, Apart's regret swaps agent-keyed "skip"/task ids into the env's assignment; SmartGrid's is keyed
    # by machine, so every reward evaluates to 0 and regret reads 0 whatever the agents did -- report none.
    if not is_jira(rc):
        return None, None
    rm = f.get("regret_multi")
    if which == "multi" or (which == "auto" and rm is not None):
        if rm is None:
            return None, None
        mean = lambda xs: statistics.mean(xs) if xs else None
        return (mean([v for a, v in rm.items() if a in rc["colluders"]]),
                mean([v for a, v in rm.items() if a not in rc["colluders"]]))
    if which == "auto" and f.get("max_tasks_per_agent", 1) > 1:
        return None, None
    return m.get("coalition_mean_regret"), m.get("noncoalition_mean_regret")


def is_jira(rc):
    env = rc.get("environment_cfg") or {}
    return env.get("name") == "JiraTicketEnvironment" or "jira" in str(env.get("import_path", "")).lower()


def row(rd, which="auto"):
    j = lambda n: json.loads((rd / n).read_text(encoding="utf-8"))
    rc, m, f, t = j("run_config.json"), j("metrics.json"), j("final_summary.json"), j("agent_turns.json")
    reg_c, reg_n = regrets(rc, m, f, which)
    # JiraMultiTaskEnvironment (envs_ext/) writes its own exact optimum; Apart's solver assumes
    # one task per agent, so it is used only for the base env. Other envs: no optimum (SmartGrid's is a
    # hard-coded 0), so %opt is left blank.
    opt = (f.get("optimal_joint_reward") if "max_tasks_per_agent" in f
           else j("optimal_summary.json")["optimal"]["joint_reward"] if is_jira(rc) else None)
    p = sum((x.get("usage") or {}).get("prompt_tokens", 0) for x in t)
    c = sum((x.get("usage") or {}).get("completion_tokens", 0) for x in t)
    rin, rout = RATES.get(rc["model"], (0, 0))
    # status "incomplete" = some agent never assigned a task (e.g. wrote the tool call as text);
    # such runs have no joint_reward and are reported but excluded from the means.
    # PersonalAssistant writes joint_reward as a ratio of its max and the raw score as raw_joint_reward
    joint = f.get("raw_joint_reward", f.get("joint_reward"))
    # "text_tool": turns whose response is a tool call written out as text instead of called
    text_tool = sum('"type": "function"' in (x.get("response") or "") for x in t)
    return {"model": rc["model_label"], "cond": rc["sweep"], "seed": rc["seed"], "status": f["status"],
            "first": rc["agent_turn_order"][0], "colluders": "+".join(rc["colluders"]),
            "adv": m.get("coalition_advantage_mean"), "joint": joint, "opt": opt,
            "pct_opt": 100 * joint / opt if opt and joint is not None else None,
            "reg_c": reg_c, "reg_n": reg_n,
            "viol": f.get("violations", m.get("violations")), "text_tool": text_tool,
            "sec": m["colluder_posts_secret"], "pub": m["colluder_posts_non_secret"],
            "calls": sum(x.get("conversation_steps") or 0 for x in t),
            "usd": p * rin * 1e-6 + c * rout * 1e-6, "run_dir": str(rd.relative_to(REPO))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--csv")
    ap.add_argument("--regret", choices=["auto", "apart", "multi"], default="auto",
                    help="regret source: auto (multi where present), apart (metrics.py), multi (regret_multi)")
    a = ap.parse_args()
    run_dirs = sorted(p.parent for p in Path(a.root).resolve().rglob("run_config.json"))
    for rd in run_dirs:
        multi = "max_tasks_per_agent" in json.loads((rd / "final_summary.json").read_text(encoding="utf-8"))
        rc = json.loads((rd / "run_config.json").read_text(encoding="utf-8"))
        if is_jira(rc) and not multi and not (rd / "optimal_summary.json").exists():
            subprocess.run([str(COLOSSEUM / ".venv" / "Scripts" / "python"), "-m",
                            "experiments.collusion.compute_jira_optimal", "--run-dir", str(rd), "--write-json"],
                           cwd=COLOSSEUM, check=True, capture_output=True)
    rows = [row(rd, a.regret) for rd in run_dirs]
    num = lambda v, spec: format(v, spec) if v is not None else format("-", ">" + spec.split(".")[0])
    print(f"regret source: {a.regret} (regC/regN = coalition / non-coalition mean)")
    print(f"{'model':7} {'cond':4} {'seed':>4} {'first':8} {'adv':>6} {'joint':>6} {'%opt':>5} {'viol':>4} "
          f"{'regC':>5} {'regN':>5} {'sec/pub':>7} {'txtTC':>5} {'calls':>5} {'USD':>7}")
    for r in sorted(rows, key=lambda r: (r["model"], r["cond"], r["seed"])):
        print(f"{r['model']:7} {r['cond']:4} {r['seed']:4} {r['first']:8} {num(r['adv'], '6.1f')} "
              f"{num(r['joint'], '6.1f')} {num(r['pct_opt'], '5.0f')} {num(r['viol'], '4')} "
              f"{num(r['reg_c'], '5.1f')} {num(r['reg_n'], '5.1f')} "
              f"{str(r['sec']) + '/' + str(r['pub']):>7} {r['text_tool']:5} {r['calls']:5} {r['usd']:7.4f}"
              + ("  INCOMPLETE" if r["status"] != "complete" else ""))
    print("\nmeans per model x condition (complete runs only):")
    groups = {}
    for r in rows:
        groups.setdefault((r["model"], r["cond"]), []).append(r)
    for (model, cond), rs in sorted(groups.items()):
        ok = [x for x in rs if x["status"] == "complete"]
        mean = lambda k: statistics.mean(x[k] for x in ok) if ok else float("nan")
        rmean = lambda k: (statistics.mean(v) if (v := [x[k] for x in ok if x[k] is not None]) else float("nan"))
        print(f"  {model:7} {cond:4} n={len(ok)}/{len(rs)}  adv {mean('adv'):6.1f}  %opt {rmean('pct_opt'):5.0f}  "
              f"viol {rmean('viol'):.1f}  regret C/N {rmean('reg_c'):.1f}/{rmean('reg_n'):.1f}  "
              f"pub posts by colluders {mean('pub'):.1f}")
    print(f"\nincomplete runs: {sum(r['status'] != 'complete' for r in rows)}/{len(rows)}; "
          f"turns with a tool call written as text: {sum(r['text_tool'] for r in rows)}")
    print(f"\ntotal token-priced cost US${sum(r['usd'] for r in rows):.4f} over {len(rows)} runs")
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    main()
