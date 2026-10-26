"""SmartGrid where an agent keeps its execution turn until its machines are assigned -- in-sprint 24 Oct 2026
. Why and how: envs_ext/multiturn.py (journal 24). Scoring, prompts and tools are Apart's base
SmartGridEnvironment, unchanged.

Wiring, with no edits to the installed packages: config `environment.import_path:
smartgrid_multiturn_env:SmartGridMultiTurnEnvironment`, this directory on PYTHONPATH.
"""
from __future__ import annotations

from envs.dcops.smart_grid.smart_grid_env import SmartGridEnvironment

from multiturn import wrap_execution


class SmartGridMultiTurnEnvironment(SmartGridEnvironment):
    tools_environment_name = "SmartGridEnvironment"

    def __init__(self, communication_protocol, config, tool_logger):
        super().__init__(communication_protocol, config, tool_logger)
        wrap_execution(self, communication_protocol)
