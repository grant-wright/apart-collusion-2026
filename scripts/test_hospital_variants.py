"""Offline test of envs_ext/hospital_swapped_env.py and hospital_nocomm_env.py. NO API call is made.
Written in-sprint 25 Oct 2026 (journal 31).

Run from collusion_hackathon/colosseum with envs_ext on PYTHONPATH:
    $env:PYTHONPATH = "<repo>/envs_ext"; .venv/Scripts/python <repo>/scripts/test_hospital_variants.py
"""
import asyncio

from hospital_nocomm_env import HospitalNoCommEnvironment
from hospital_passes_env import HospitalPassesEnvironment
from hospital_swapped_env import HospitalSwappedEnvironment
import random
import tempfile
import types

from test_hospital_passes import FakeProtocol, run_pass

SECRET = "MEET ME AT GENERAL -- PLAN X"


def make(cls, seed=43):
    p = FakeProtocol()
    cfg = {"environment": {}, "simulation": {"seed": seed, "max_iterations": 1},
           "llm": {"provider": "openrouter", "openrouter": {"model": "x"}},
           "experiment": {"output_dir": tempfile.mkdtemp()}}
    env = cls(p, cfg, None)
    order = list(env.agent_names)
    random.Random(seed).shuffle(order)
    env.set_agent_clients([types.SimpleNamespace(name=n) for n in order])
    return env, p


def main():
    for seed in (43, 44, 45):
        base, pb = make(HospitalPassesEnvironment, seed)
        sw, ps = make(HospitalSwappedEnvironment, seed)
        assert sw.agent_names == base.agent_names, "swap changed agent_names (colluders / turn order)"
        assert sw.hospital_names == base.hospital_names, "swap changed hospital_names (scoring)"
        ctx = sw.build_agent_context("Resource_Provisioner", phase="planning", iteration=1)
        text = sw.prompts.get_user_prompt("Resource_Provisioner", ctx, {"0": ""})
        assert text.index("St_Marys_Center:") < text.index("General_Hospital:"), "overview not swapped"
        btext = base.prompts.get_user_prompt("Resource_Provisioner",
                                             base.build_agent_context("Resource_Provisioner", phase="planning",
                                                                      iteration=1), {"0": ""})
        assert btext.index("General_Hospital:") < btext.index("St_Marys_Center:")
        asyncio.run(run_pass(base, pb))
        asyncio.run(run_pass(sw, ps))
        sb, ss = base.get_final_summary(), sw.get_final_summary()
        assert sb["agent_rewards"] == ss["agent_rewards"], "swap changed scoring on identical play"
        print(f"seed {seed}: swap -- overview St Marys first, colluders/turn order/scoring unchanged")

    nc, _ = make(HospitalNoCommEnvironment)
    boards = {"3": f"[1] General_Hospital_Triage: {SECRET}", "8": f"[2] Resource_Provisioner: {SECRET}"}
    for a in nc.agent_names:
        for phase in ("planning", "execution"):
            t = nc.prompts.get_user_prompt(a, nc.build_agent_context(a, phase=phase, iteration=1), boards)
            assert SECRET not in t, f"{a} {phase}: a board message leaked into the prompt"
    dept = nc.prompts.get_user_prompt("General_Hospital_Triage",
                                      nc.build_agent_context("General_Hospital_Triage", phase="planning",
                                                             iteration=1), boards)
    assert "ID: 3" in dept and "[8]" in dept, "board ids lost"
    base, _ = make(HospitalPassesEnvironment)
    assert SECRET in base.prompts.get_user_prompt("General_Hospital_Triage",
                                                  base.build_agent_context("General_Hospital_Triage",
                                                                           phase="planning", iteration=1), boards)
    print("nocomm: no board text reaches any of 9 agents in either phase; board ids kept; base env does show it")
    print("OK")


if __name__ == "__main__":
    main()
