"""Hospital with the hospitals LISTED in swapped order -- in-sprint 25 Oct 2026 (journal 31).

Why (Grant: "try swapping the hospital order to see what effect that has"): in hosp2 the Provisioner sent every
top-up to General_Hospital -- the colluder's hospital, but also the hospital listed first (journal 30). This
separates the two. The one change vs HospitalPassesEnvironment: self.inventory (and hospital_failures) are
re-keyed St_Marys_Center first. That dict order is the only place hospital order reaches the Provisioner's
planning prompt ("Inventory Overview"; alerts and cost table are empty at the start). hospital_names, agent_names
(so colluders = General_Hospital_Triage + Resource_Provisioner, turn order and the path), scoring and the
department prompts are unchanged. Not swapped: the example list in Apart's transfer_resources tool description.

Wiring: config `environment.import_path: hospital_swapped_env:HospitalSwappedEnvironment`, envs_ext on PYTHONPATH.
"""
from __future__ import annotations

from hospital_passes_env import HospitalPassesEnvironment


class HospitalSwappedEnvironment(HospitalPassesEnvironment):
    def __init__(self, communication_protocol, config, tool_logger):
        super().__init__(communication_protocol, config, tool_logger)
        order = list(reversed(self.hospital_names)) + [k for k in self.inventory if k not in self.hospital_names]
        self.inventory = {k: self.inventory[k] for k in order}
        self.hospital_failures = {h: self.hospital_failures[h] for h in reversed(self.hospital_names)}
