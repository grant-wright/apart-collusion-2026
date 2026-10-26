"""Offline test of envs_ext/smartgrid_truerule_env.py. NO API call is made.
Written in-sprint 25 Oct 2026 (journal 28).

Run from collusion_hackathon/colosseum with envs_ext on PYTHONPATH:
    $env:PYTHONPATH = "<repo>/envs_ext"; .venv/Scripts/python <repo>/scripts/test_smartgrid_truerule.py
Checks, on the seeds we run: every agent's instructions lose the misstatement and gain the true rule (and the
no-targeting rule for the -nt class); everything else in the instructions is unchanged; scoring is unchanged
(same joint and per-agent rewards as SmartGridMultiTurnEnvironment on random full assignments); and the true
rule's wording matches _rewards() (per-agent reward = - sum over connected sources of overflow / clients).
"""
import random
import tempfile

from smartgrid_multiturn_env import SmartGridMultiTurnEnvironment
from smartgrid_truerule_env import (MISSTATEMENT, NO_TARGETING_RULE, TRUE_RULE, SmartGridNoTargetingEnvironment,
                                    SmartGridTrueRuleEnvironment)


def build(cls, seed):
    cfg = {"environment": {"assignment_filling": False},
           "simulation": {"seed": seed, "max_iterations": 1},
           "communication_network": {"num_agents": 4, "topology": "path"},
           "llm": {"provider": "openrouter", "openrouter": {"model": "x"}},
           "experiment": {"output_dir": tempfile.mkdtemp()}}
    stub = type("StubProtocol", (), {"agent_execution_turn": lambda self, *a: None})()
    return cls(stub, cfg, None)


def main():
    for seed in (37, 38, 39):
        base = build(SmartGridMultiTurnEnvironment, seed)
        for cls, rules in ((SmartGridTrueRuleEnvironment, (TRUE_RULE,)),
                           (SmartGridNoTargetingEnvironment, (TRUE_RULE, NO_TARGETING_RULE))):
            env = build(cls, seed)
            for a in env.agent_names:
                old, new = base.instance.instructions[a], env.instance.instructions[a]
                assert MISSTATEMENT in old and MISSTATEMENT not in new
                assert new == old.replace(MISSTATEMENT, "\n".join(rules)), a
            rng = random.Random(seed)
            for _ in range(200):
                acts = {name: rng.choice(v.domain) for name, v in env.problem.variables.items()}
                assert env._rewards(acts) == base._rewards(acts)
                # the stated rule, computed independently of _rewards()
                _, local = env._rewards(acts)
                for a in env.agent_names:
                    charge = 0.0
                    for f in env.problem.factors:
                        if f.name.startswith("overflow_"):
                            owners = {env.problem.variables[v].owner for v in f.scope}
                            if a in owners:
                                charge += f.evaluate(acts) / len(owners)
                    assert abs(local[a] - charge) < 1e-9, (seed, a, local[a], charge)
            print(f"seed {seed} {cls.__name__}: {len(env.agent_names)} agents' instructions changed; "
                  f"scoring identical on 200 random assignments; stated rule matches _rewards()")
    print("OK")


if __name__ == "__main__":
    main()
