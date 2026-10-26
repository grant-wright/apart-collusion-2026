"""Hospital with NO communication between any agents -- in-sprint 25 Oct 2026 (journal 31).

Why (Grant: "could it be that the innocents are not innocent and are colluding? ... can you run a sim where there
is no communication between any of the agents at all"): a baseline for what the environment and turn order alone
produce. If the reward pattern of A (or E) also appears here, no one's coordination is needed to explain it.

What: agents see other agents' messages only through `blackboard_context` in the user prompt (Terrarium gives
them post_message but no read tool). This env's prompts pass every board through with its text blanked -- board
ids kept, so the prompt layout and post_message targets are unchanged, but nothing anyone posts (nor the env's
action echoes on the boards) ever reaches another agent. Run with the E config (coalition_prompt never), so the
one change vs hosp2 E is the blanked boards. Shared ENVIRONMENT state still couples agents (a department's job
queue shows a patient once the earlier step is booked) -- that is the task, not communication.

Wiring: config `environment.import_path: hospital_nocomm_env:HospitalNoCommEnvironment`, envs_ext on PYTHONPATH.
"""
from __future__ import annotations

from envs.dcops.hospital.hospital_prompts import HospitalPrompts

from hospital_passes_env import HospitalPassesEnvironment


class NoCommHospitalPrompts(HospitalPrompts):
    def get_user_prompt(self, agent_name, agent_context, blackboard_context):
        blank = {k: "" for k in (blackboard_context or {})}
        return super().get_user_prompt(agent_name, agent_context, blank)


class HospitalNoCommEnvironment(HospitalPassesEnvironment):
    def __init__(self, communication_protocol, config, tool_logger):
        super().__init__(communication_protocol, config, tool_logger)
        self.prompts = NoCommHospitalPrompts(self, self.full_config)
