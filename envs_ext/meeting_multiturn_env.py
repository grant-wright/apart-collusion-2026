"""MeetingScheduling where an agent keeps its execution turn until its attendances are set -- in-sprint 24 Oct
2026. Why and how: envs_ext/multiturn.py (journal 24, 26). Scoring, prompts and tools are Apart's
base MeetingSchedulingEnvironment, unchanged.

Wiring, with no edits to the installed packages: config `environment.import_path:
meeting_multiturn_env:MeetingSchedulingMultiTurnEnvironment`, this directory on PYTHONPATH.
"""
from __future__ import annotations

from envs.dcops.meeting_scheduling.meeting_scheduling_env import MeetingSchedulingEnvironment

from multiturn import wrap_execution


class MeetingSchedulingMultiTurnEnvironment(MeetingSchedulingEnvironment):
    tools_environment_name = "MeetingSchedulingEnvironment"

    def __init__(self, communication_protocol, config, tool_logger):
        super().__init__(communication_protocol, config, tool_logger)
        wrap_execution(self, communication_protocol)
