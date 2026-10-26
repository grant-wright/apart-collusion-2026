"""Hospital with per-agent rewards and repeated execution passes -- in-sprint 25 Oct 2026 (journal 30).

Why: run.py gives ONE execution pass with each agent's context built once, and Terrarium ends a turn on the first
committed env call, so a department books at most one patient; a later step (Radiology after Triage, ...) is only
in a department's job queue once the earlier step is booked. Offline screen (scripts/hospital_screen.py, greedy
stand-in): stock completes ~1 of 8 patients; repeat turns per agent alone ~4 of 8 with turn order swinging the
advantage by +-1000; repeated full passes 8 of 8.

What: (1) get_final_summary() adds `agent_rewards` = the env's own exact decomposition of the joint reward
(_calculate_makespan_and_flow; metrics.py reads it -- base Hospital exposes neither it nor _rewards()).
(2) An agent keeps its execution turn while each turn books a new step, with a FRESH context per turn (the job
queue changes as steps are booked), up to its queue length + 1 turns. After the last agent in turn order, if pass 1
booked anything, further passes run over env.agents -- departments with a non-empty queue, plus the Resource_Provisioner -- until a pass
books nothing, MAX_PASSES passes in all. Progress counts bookings only, never transfers (a hospital-to-hospital
transfer pays the sender +15/unit, so counting it would let a ping-pong keep the loop alive). run.py's collusion
fields (role, coalition, private board) are carried into every rebuilt context. Usage of the extra passes is
summed into the last agent's turn record (run totals stay right); each extra turn is listed in the summary's
`extra_execution_turns`. (3) Integer tool arguments sent as strings are coerced (see _ints). Scoring, prompts and
tools are Apart's base HospitalEnvironment, unchanged.

Wiring, with no edits to the installed packages: config `environment.import_path:
hospital_passes_env:HospitalPassesEnvironment`, this directory on PYTHONPATH.
"""
from __future__ import annotations

from typing import Any, Dict, List

from envs.dcops.hospital.hospital_env import HospitalEnvironment

MAX_PASSES = 6


class HospitalPassesEnvironment(HospitalEnvironment):
    tools_environment_name = "HospitalEnvironment"

    def __init__(self, communication_protocol, config, tool_logger):
        super().__init__(communication_protocol, config, tool_logger)
        self.extra_execution_turns: List[Dict[str, Any]] = []
        self._wrap_execution(communication_protocol)

    # Llama-70B sends the integer tool arguments as strings ("0", "9"); the base env compares them with ints, raises
    # TypeError, and the action is silently dropped -- in the first batch (runs/hosp/, invalid) no booking or
    # transfer took effect (journal 30). Coerce; drop the action, as the base does for bad input, if it won't parse.
    @staticmethod
    def _ints(action, keys):
        out = dict(action)
        for k in keys:
            if k in out:
                try:
                    out[k] = int(float(str(out[k]).strip()))
                except (TypeError, ValueError):
                    return None
        return out

    def _process_schedule_request(self, agent_id, action):
        action = self._ints(action, ("step_index", "start_time"))
        if action is not None:
            super()._process_schedule_request(agent_id, action)

    def _process_transfer(self, sender_id, action):
        action = self._ints(action, ("amount",))
        if action is not None:
            super()._process_transfer(sender_id, action)

    def _booked(self) -> int:
        return sum(len(s["scheduled_steps"]) for s in self.patient_states.values())

    def _queue(self, agent_name) -> list:
        return self.build_agent_context(agent_name, phase="execution", iteration=1).get("job_queue") or []

    def _wrap_execution(self, protocol) -> None:
        single_turn = protocol.agent_execution_turn
        extras: Dict[str, Dict[str, Any]] = {}   # run.py's collusion fields, per agent
        pass1_start: List[int] = []              # bookings before pass 1

        def fresh(agent_name):
            return {**self.build_agent_context(agent_name, phase="execution", iteration=1), **extras[agent_name]}

        async def agent_turns(agent, agent_name, context, iteration):
            """One agent's turns: repeat while each turn books a new step. Returns summed record, booked count."""
            total: Dict[str, Any] = {}
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            steps = tools = turns = 0
            start = self._booked()
            limit = len(self._queue(agent_name)) + 1
            while turns < limit:
                before = self._booked()
                total = await single_turn(agent, agent_name, context, self, iteration) or {}
                turns += 1
                for k in usage:
                    usage[k] += (total.get("usage") or {}).get(k, 0) or 0
                steps += total.get("conversation_steps") or 0
                tools += total.get("tools_executed") or 0
                if self._booked() == before or not self._queue(agent_name):
                    break
                context = fresh(agent_name)
            return ({**total, "usage": usage, "conversation_steps": steps, "tools_executed": tools,
                     "execution_turns": turns}, self._booked() - start)

        async def execution_turn(agent, agent_name, agent_context, environment, iteration):
            if not extras:
                pass1_start.append(self._booked())
            base = self.build_agent_context(agent_name, phase="execution", iteration=1)
            extras[agent_name] = {k: v for k, v in agent_context.items() if k not in base}
            record, _ = await agent_turns(agent, agent_name, agent_context, iteration)
            order = list(getattr(self, "agents", []) or [])
            if not order or order[-1].name != agent_name or self._booked() == pass1_start[0]:
                return record
            # Last agent of pass 1: run the further passes here, folding their usage into this record.
            for p in range(2, MAX_PASSES + 1):
                booked = 0
                for ag in order:
                    if ag.name != "Resource_Provisioner" and not self._queue(ag.name):
                        continue
                    rec, n = await agent_turns(ag, ag.name, fresh(ag.name), iteration)
                    booked += n
                    self.extra_execution_turns.append({"pass": p, "agent": ag.name, "booked": n,
                                                       "usage": rec.get("usage"),
                                                       "execution_turns": rec.get("execution_turns"),
                                                       "response": rec.get("response")})
                    for k in record["usage"]:
                        record["usage"][k] += (rec.get("usage") or {}).get(k, 0) or 0
                    for k in ("conversation_steps", "tools_executed", "execution_turns"):
                        record[k] = (record.get(k) or 0) + (rec.get(k) or 0)
                if booked == 0:
                    break
            return record

        protocol.agent_execution_turn = execution_turn

    def get_final_summary(self):
        summary = super().get_final_summary()
        _, rewards = self._calculate_makespan_and_flow()
        summary["agent_rewards"] = {a: float(v) for a, v in rewards.items()}
        summary["extra_execution_turns"] = self.extra_execution_turns
        return summary
