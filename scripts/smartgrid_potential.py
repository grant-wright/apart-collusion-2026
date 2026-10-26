"""Offline: how much room SmartGrid gives a coalition, per seed. NO API call is made.
Written in-sprint 24 Oct 2026.

Run from collusion_hackathon/colosseum:
    .venv/Scripts/python <repo>/scripts/smartgrid_potential.py 37 38 39 ...
Builds the same instance a run would (4 agents, env defaults, same seed), colluders = first and last of
env.agent_names (run.py `first_and_last`). Scoring is the env's own _rewards(): each source's overflow is
split EQUALLY among that source's clients, whoever caused it. Reports, per seed:
  joint  = a joint optimum (min total overflow) and the coalition advantage there;
  br     = the coalition's best response with the innocents held at that joint optimum;
  gain   = advantage(br) - advantage(joint), i.e. how far collusion alone can move the advantage.
Both searches are heuristic (coordinate ascent, random restarts), not exact -- label numbers as such.
Advantage = colluders' mean reward minus the innocents' mean (same as summarise_runs.py).
"""
import random
import sys
import tempfile
import types

from envs.dcops.meeting_scheduling.meeting_scheduling_env import MeetingSchedulingEnvironment
from envs.dcops.personal_assistant.personal_assistant_env import PersonalAssistantEnvironment
from envs.dcops.smart_grid.smart_grid_env import SmartGridEnvironment

RESTARTS = 30
# --env meeting|pa (journal 26): same screen on MeetingScheduling / PersonalAssistant at env defaults.
ENVS = {"smartgrid": SmartGridEnvironment, "meeting": MeetingSchedulingEnvironment,
        "pa": PersonalAssistantEnvironment}


def build(seed, cls=SmartGridEnvironment):
    cfg = {"environment": {"assignment_filling": False},
           "simulation": {"seed": seed, "max_iterations": 1},
           "communication_network": {"num_agents": 4, "topology": "path"},
           "llm": {"provider": "openrouter", "openrouter": {"model": "x"}},
           "experiment": {"output_dir": tempfile.mkdtemp()}}
    return cls(types.SimpleNamespace(), cfg, None)


def ascend(env, free, start, objective, rng):
    best, best_val = None, float("-inf")
    for _ in range(RESTARTS):
        a = dict(start)
        for v in free:
            a[v] = rng.choice(env.problem.variables[v].domain)
        improved = True
        while improved:
            improved = False
            for v in rng.sample(free, len(free)):
                cur = a[v]
                top_d, top_val = cur, objective(a)
                for d in env.problem.variables[v].domain:
                    if d == cur:
                        continue
                    a[v] = d
                    val = objective(a)
                    if val > top_val + 1e-9:
                        top_d, top_val = d, val
                a[v] = top_d
                improved |= top_d != cur
        val = objective(a)
        if val > best_val:
            best, best_val = a, val
    return best


def advantage(rewards, colluders):
    inn = [r for a, r in rewards.items() if a not in colluders]
    col = [rewards[a] for a in colluders]
    return sum(col) / len(col) - sum(inn) / len(inn)


def main():
    args = sys.argv[1:]
    cls = SmartGridEnvironment
    if "--env" in args:
        i = args.index("--env")
        cls = ENVS[args[i + 1]]
        del args[i:i + 2]
    for seed in [int(s) for s in args]:
        env = build(seed, cls)
        rng = random.Random(seed)
        names = env.agent_names
        colluders = {names[0], names[-1]}
        allv = list(env.problem.variables)
        colv = [v for v in allv if env.problem.variables[v].owner in colluders]

        joint = ascend(env, allv, {}, lambda a: env._rewards(a)[0], rng)
        j_total, j_rew = env._rewards(joint)
        br = ascend(env, colv, {v: joint[v] for v in allv if v not in colv},
                    lambda a: sum(env._rewards(a)[1][c] for c in colluders), rng)
        b_total, b_rew = env._rewards(br)

        n_vars = {a: len(env.problem.agent_variables(a)) for a in names}
        print(f"seed {seed}: agents {names} (colluders {sorted(colluders)}), variables {n_vars}")
        if cls is SmartGridEnvironment:
            src = {s: [c[:3] + ("*" if c in colluders else "") for c in spec.clients]
                   for s, spec in env.instance.sources.items()}
            print(f"  sources: {src}")
        elif cls is PersonalAssistantEnvironment:
            print("  pair factors: " + "; ".join(
                f.name for f in env.problem.factors if f.factor_type == "coordination"))
        else:
            print("  meetings: " + "; ".join(
                f"{m.meeting_id} {m.meeting_type} {m.start}-{m.end} "
                + ",".join(p[:3] + ("*" if p in colluders else "") for p in m.participants)
                for m in env.instance.meetings))
        coal = lambda r: sum(r[c] for c in colluders)
        # joint reward is -overflow in SmartGrid; reported as is (higher is better) for both envs
        print(f"  joint: total {j_total:7.2f}  coalition {coal(j_rew):7.2f}  adv {advantage(j_rew, colluders):+6.2f}"
              f"   br: total {b_total:7.2f}  coalition {coal(b_rew):7.2f}  adv {advantage(b_rew, colluders):+6.2f}"
              f"   gain adv {advantage(b_rew, colluders) - advantage(j_rew, colluders):+6.2f}"
              f"  coalition {coal(b_rew) - coal(j_rew):+6.2f}")


if __name__ == "__main__":
    main()
