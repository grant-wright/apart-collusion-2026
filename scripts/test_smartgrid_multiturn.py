"""Offline test of envs_ext/smartgrid_multiturn_env.py. NO API call is made.
Written in-sprint 24 Oct 2026.

Run from collusion_hackathon/colosseum with envs_ext on PYTHONPATH:
    $env:PYTHONPATH = "<repo>/envs_ext"; .venv/Scripts/python <repo>/scripts/test_smartgrid_multiturn.py
A fake protocol stands in for the LLM turn: each call assigns ONE of the agent's machines (as Llama-70B did).
"""
import asyncio
import tempfile

from meeting_multiturn_env import MeetingSchedulingMultiTurnEnvironment
from smartgrid_multiturn_env import SmartGridMultiTurnEnvironment


class FakeProtocol:
    def __init__(self, stall_after=None):
        self.calls, self.stall_after = 0, stall_after

    async def agent_execution_turn(self, agent, agent_name, agent_context, environment, iteration):
        self.calls += 1
        if self.stall_after is None or self.calls <= self.stall_after:
            for v in environment.problem.agent_variables(agent_name):
                if v.name not in environment.assignment:
                    environment.assignment[v.name] = v.domain[0]
                    break
        return {"usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11},
                "conversation_steps": 1, "tools_executed": 1, "response": f"call {self.calls}"}


def build(protocol, cls):
    cfg = {"environment": {"assignment_filling": False},
           "simulation": {"seed": 37, "max_iterations": 1},
           "communication_network": {"num_agents": 4, "topology": "path"},
           "llm": {"provider": "openrouter", "openrouter": {"model": "x"}},
           "experiment": {"output_dir": tempfile.mkdtemp()}}
    return cls(protocol, cfg, None)


def main():
    # (journal 26): the same test for MeetingScheduling via the shared envs_ext/multiturn.py helper
    for cls in (SmartGridMultiTurnEnvironment, MeetingSchedulingMultiTurnEnvironment):
        check(cls)


def check(cls):
    print(cls.__name__)
    p = FakeProtocol()
    env = build(p, cls)
    for name in env.agent_names:
        n = len(env.problem.agent_variables(name))
        before = p.calls
        r = asyncio.run(p.agent_execution_turn(None, name, {}, env, 1))
        assert p.calls - before == n, (name, p.calls - before, n)
        assert r["execution_turns"] == n and r["conversation_steps"] == n and r["usage"]["prompt_tokens"] == 10 * n
    assert len(env.assignment) == len(env.problem.variables)
    assert env.get_final_summary()["status"] == "complete"
    print(f"  all {len(env.assignment)} variables assigned; one turn per variable")

    p = FakeProtocol(stall_after=1)
    env = build(p, cls)
    name = env.agent_names[0]
    r = asyncio.run(p.agent_execution_turn(None, name, {}, env, 1))
    assert r["execution_turns"] == 2 and len(env.assignment) == 1, r
    print("  stalled agent: stops after the first turn that assigns nothing")


if __name__ == "__main__":
    main()
