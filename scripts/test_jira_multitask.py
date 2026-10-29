"""Offline test of envs_ext/jira_multitask_env.py (no model calls) -- in-sprint 24 Oct 2026.

Run from collusion_hackathon/colosseum with envs_ext on PYTHONPATH:
    $env:PYTHONPATH = "<repo>/envs_ext"; .venv/Scripts/python <repo>/scripts/test_jira_multitask.py
Checks the tool's accept/reject paths, that scoring with one task each matches the base env exactly, the
cap-2 optimum against brute force, regret_multi against brute force (cap 2) and Apart's regret (cap 1),
and that every one-task phrase in the prompts was rewritten.
"""
import itertools
import tempfile
import types

from envs.dcops.jira_ticket.jira_ticket_env import JiraTicketEnvironment
from terrarium.environment_tools import instantiate_environment_tools

import jira_multitask_env as m


def make(cls, seed=3, max_tasks=6):
    cfg = {"environment": {"name": cls.__name__, "max_tasks": max_tasks, "max_tasks_per_agent": 2,
                           "assignment_filling": False},
           "simulation": {"seed": seed, "max_iterations": 1},
           "communication_network": {"num_agents": 4, "topology": "path"},
           "llm": {"provider": "openrouter", "openrouter": {"model": "x"}},
           "experiment": {"output_dir": tempfile.mkdtemp()}}
    return cls(types.SimpleNamespace(), cfg, None)


def main():
    env = make(m.JiraMultiTaskEnvironment)
    base = make(JiraTicketEnvironment)
    assert list(env.tasks) == list(base.tasks) and env.costs == base.costs, "same seed must give same instance"
    a, b, c, d = env.agent_names
    t = list(env.tasks)

    tools = instantiate_environment_tools(env.tools_environment_name, None)
    assert isinstance(tools, m.JiraMultiTaskTools)
    call = lambda agent, args: tools.handle_tool_call("assign_task", agent, args, env_state=env.get_serializable_state())
    assert call(a, {"task_ids": t[:3]})["status"] == "retry"                      # over the cap
    assert call(a, {"task_ids": ["nope"]})["status"] == "retry"                   # unknown id
    assert call(a, {"task_ids": ["skip", t[0]]})["status"] == "retry"             # skip mixed in
    r = call(a, {"task_ids": t[:2]})
    assert r["status"] == "success" and r["result"]["state_updates"] == {"assignment": {a: t[:2]}}, r
    env.apply_state_updates(r["result"]["state_updates"])
    assert call(a, {"task_ids": [t[2]]})["status"] == "failed"                    # already committed
    r = call(b, {"task_id": f"{t[2]}, {t[2]}"})                                   # legacy string, deduped
    assert r["result"]["state_updates"] == {"assignment": {b: [t[2]]}}, r
    assert call(c, {"task_ids": ["skip"]})["result"]["state_updates"] == {"assignment": {c: None}}

    # One task each: identical to the base env (score and per-agent rewards).
    single = {a: t[0], b: t[1], c: None, d: t[1]}                                 # incl. a duplicate
    listed = {k: ([v] if v else None) for k, v in single.items()}
    assert env._rewards(listed) == base._rewards(single), (env._rewards(listed), base._rewards(single))
    assert env._rewards(single) == base._rewards(single)                          # bare ids accepted too

    # Two tasks: per-agent reward is the sum of its tasks' base rewards.
    two = {a: [t[0], t[1]], b: [t[2]], c: None, d: None}
    _, loc = env._rewards(two)
    want = sum(base._rewards({a: x, b: None, c: None, d: None})[1][a] for x in (t[0], t[1]))
    assert abs(loc[a] - want) < 1e-9, (loc[a], want)

    # Optimum vs brute force over every task -> (agent or nobody), cap 2.
    best = float("-inf")
    for owners in itertools.product([None] + env.agent_names, repeat=len(t)):
        if any(owners.count(x) > 2 for x in env.agent_names):
            continue
        acts = {x: [tid for tid, o in zip(t, owners) if o == x] or None for x in env.agent_names}
        best = max(best, env._evaluate_assignment(acts)["score"])
    opt = env.compute_optimal_joint_reward()
    assert abs(opt - best) < 1e-6, (opt, best)

    # regret_multi vs brute force: every subset of tasks by bitmask, size <= 2, others fixed.
    profiles = [{a: [t[0]], b: [t[0], t[3]], c: None, d: [t[4]]},                  # duplicate + skip
                {a: [t[1]], b: None, c: [t[2]], d: [t[5], t[1]]},
                {a: None, b: None, c: None, d: None}]
    for acts in profiles:
        got = env.compute_regret_multi(acts)
        for x in env.agent_names:
            own = lambda claim: env._rewards({**acts, x: claim})[1][x]
            subsets = [[tid for i, tid in enumerate(t) if mask >> i & 1] for mask in range(2 ** len(t))]
            best = max(own(s or None) for s in subsets if len(s) <= 2)
            assert abs(got[x] - max(0.0, best - own(acts[x]))) < 1e-9, (x, got[x], best)
    assert any(v > 0 for v in env.compute_regret_multi(profiles[0]).values())

    # Cap 1: regret_multi equals Apart's metrics.py regret, agent by agent.
    from experiments.collusion.metrics import compute_collusion_metrics
    env1 = make(m.JiraMultiTaskEnvironment)
    env1.max_tasks_per_agent = 1
    nonzero = 0
    for acts in ({a: t[0], b: t[0], c: None, d: t[4]}, {a: t[1], b: t[2], c: t[3], d: t[5]}, {a: t[2]}):
        apart = compute_collusion_metrics(env=env1, colluders=[a, d], secret_blackboard_id=None,
                                          secret_channel_enabled=False, prompt_variant="x", tool_events=[],
                                          final_summary={"assignment": acts, "joint_reward": None})
        ours = env1.compute_regret_multi(acts)
        for o in apart.agents:
            assert o.regret is not None and abs(o.regret - ours[o.agent_name]) < 1e-9, (o.agent_name, o.regret, ours)
            nonzero += o.regret > 0
    assert nonzero, "cap-1 comparison must include non-zero regrets"

    # Prompts: no one-task wording left.
    env.assignment = {}
    sys_p = env.prompts.get_system_prompt()
    assert "at most one" not in sys_p and "up to 2 tasks" in sys_p, sys_p
    assert "at most one" not in env.get_network_context()
    print(f"all checks pass (optimum {opt:.2f} = brute force over {len(t)} tasks)")


if __name__ == "__main__":
    main()
