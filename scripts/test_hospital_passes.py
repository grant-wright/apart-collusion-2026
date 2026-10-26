"""Offline test of envs_ext/hospital_passes_env.py. NO API call is made.
Written in-sprint 25 Oct 2026 (journal 30).

Run from collusion_hackathon/colosseum with envs_ext on PYTHONPATH:
    $env:PYTHONPATH = "<repo>/envs_ext"; .venv/Scripts/python <repo>/scripts/test_hospital_passes.py
A fake protocol stands in for the LLM turn: each call books the FIRST job in the context it was given (one
booking per call, as Llama-70B makes one env call per response), or nothing when stalled.
"""
import asyncio
import random
import tempfile
import types

from hospital_passes_env import MAX_PASSES, HospitalPassesEnvironment


class FakeProtocol:
    def __init__(self, stall=False):
        self.calls, self.stall, self.contexts = 0, stall, []

    async def agent_execution_turn(self, agent, agent_name, agent_context, environment, iteration):
        self.calls += 1
        self.contexts.append(agent_context)
        if not self.stall:
            for job in agent_context.get("job_queue") or []:
                pid, idx = job["patient_id"], job["step_index"]
                for t in range(int(job["earliest_start_time"]), environment.max_time_horizon):
                    # strings, as Llama-70B sends them (journal 30)
                    environment._process_schedule_request(agent_name, {"patient_id": pid, "step_index": str(idx),
                                                                       "start_time": str(t)})
                    if idx in environment.patient_states[pid]["scheduled_steps"]:
                        break
                break
        return {"usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11},
                "conversation_steps": 1, "tools_executed": 1, "response": f"call {self.calls}"}


def build(protocol, seed=43):
    cfg = {"environment": {}, "simulation": {"seed": seed, "max_iterations": 1},
           "llm": {"provider": "openrouter", "openrouter": {"model": "x"}},
           "experiment": {"output_dir": tempfile.mkdtemp()}}
    env = HospitalPassesEnvironment(protocol, cfg, None)
    order = list(env.agent_names)
    random.Random(seed).shuffle(order)
    env.set_agent_clients([types.SimpleNamespace(name=n) for n in order])
    return env


async def run_pass(env, protocol):
    """What run.py does: one execution turn per agent, context = base + collusion fields."""
    records = []
    for ag in env.agents:
        ctx = {**env.build_agent_context(ag.name, phase="execution", iteration=1), "collusion_role": f"r-{ag.name}"}
        records.append(await protocol.agent_execution_turn(ag, ag.name, ctx, env, iteration=1))
    return records


def main():
    for seed in (43, 44, 45):
        p = FakeProtocol()
        env = build(p, seed)
        records = asyncio.run(run_pass(env, p))
        s = env.get_final_summary()
        done = sum(len(env.patient_states[q]["scheduled_steps"]) == len(env.patients[q]["pathway"])
                   for q in env.patients)
        assert done == len(env.patients), f"seed {seed}: only {done} complete"
        assert abs(sum(s["agent_rewards"].values()) - s["joint_reward"]) < 1e-6
        assert all(c.get("collusion_role") for c in p.contexts), "a rebuilt context lost the collusion fields"
        assert all(c["collusion_role"] == f"r-{c['agent_name']}" for c in p.contexts), "fields crossed agents"
        assert sum(r["usage"]["total_tokens"] for r in records) == 11 * p.calls, "usage not all accounted for"
        passes = max([t["pass"] for t in s["extra_execution_turns"]] or [1])
        assert passes <= MAX_PASSES
        print(f"seed {seed}: {done}/8 complete, {p.calls} calls, {passes} passes, joint {s['joint_reward']:.0f}")

    p = FakeProtocol(stall=True)
    env = build(p)
    asyncio.run(run_pass(env, p))
    assert p.calls == len(env.agent_names), f"stalled agents should get one turn each, got {p.calls} calls"
    assert not env.extra_execution_turns
    print(f"stall: {p.calls} calls, no extra passes")

    env = build(FakeProtocol())
    env._process_schedule_request("General_Hospital_Triage", {"patient_id": "null", "step_index": "null",
                                                              "start_time": "null"})
    env._process_transfer("General_Hospital_Triage", {"to_hospital": "St_Marys_Center", "resource_type": "IV_Kits",
                                                      "amount": "5"})
    assert env.inventory["St_Marys_Center"]["IV_Kits"] - env.inventory["General_Hospital"]["IV_Kits"] == 10
    print("string args: 'null' booking dropped, transfer of '5' applied")
    print("OK")


if __name__ == "__main__":
    main()
