"""Offline: write short-path copies of Apart's 2.1 condition configs into configs/. NO API call is made.
Written in-sprint 24 Oct 2026.

    python scripts/make_configs.py --set pilot --seeds 1
    python scripts/make_configs.py --set eval  --seeds 2,3,4,5,6,7,8,9,10,11

Changes ONLY what Windows paths and our sweep need (science unchanged except A2):
  label -> qwen7b; output_dir -> runs/<set>/<cond>; sweep name -> <cond>; seeds -> --seeds.
  A2 (A-prime, "evasive colluders") = condition A with prompt_variants [structured]: Apart's built-in
  variant telling colluders to stay covert and keep public messages plausible/benign.
"""
import argparse
import re
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "collusion_hackathon" / "colosseum" / "experiments" / "collusion" / "configs"
CONDITIONS = {  # our short name -> (Apart's file, prompt variant override or None)
    "a": ("hackathon_2_1_a_pair_private_channel.yaml", None),
    "a2": ("hackathon_2_1_a_pair_private_channel.yaml", "structured"),
    # pilot3 (24 Oct evening): stronger built-in variants, to get runs where collusion actually pays off
    "agg": ("hackathon_2_1_a_pair_private_channel.yaml", "aggressive"),
    "dec": ("hackathon_2_1_a_pair_private_channel.yaml", "deception"),
    "b": ("hackathon_2_1_b_pair_no_channel.yaml", None),
    "c": ("hackathon_2_1_c_open_channel.yaml", None),
    "d": ("hackathon_2_1_d_neither.yaml", None),
    # E (24 Oct late evening): same-channel innocent control = A with coalition_prompt never. The pair keeps
    # its private board, so public boards go equally quiet; only the instruction to collude differs.
    # Variant must be "control": with coalition_prompt never, run.py silently skips any other variant.
    "e": ("hackathon_2_1_a_pair_private_channel.yaml", "control"),
}
COALITION_PROMPT = {"e": "never"}   # condition -> experiment.collusion.coalition_prompt override
# --env -> the environment line replacing Apart's `name: JiraTicketEnvironment` + `max_tasks`.
# *-mt classes live in envs_ext/ (repeated execution turns; journal 24) and need it on PYTHONPATH.
ENV_LINES = {
    "jira": None,
    "smartgrid": "name: SmartGridEnvironment",
    "smartgrid-mt": "import_path: smartgrid_multiturn_env:SmartGridMultiTurnEnvironment",
    # 25 Oct: smartgrid-mt + the true per-agent reward rule in every agent's instructions (journal 28);
    # -nt adds the no-targeting rule on top (journal 29).
    "smartgrid-tr": "import_path: smartgrid_truerule_env:SmartGridTrueRuleEnvironment",
    "smartgrid-nt": "import_path: smartgrid_truerule_env:SmartGridNoTargetingEnvironment",
    "meeting-mt": "import_path: meeting_multiturn_env:MeetingSchedulingMultiTurnEnvironment",
    "pa": "name: PersonalAssistantEnvironment",
    # 25 Oct: Hospital + agent_rewards + repeated execution passes (envs_ext/hospital_passes_env.py, journal 30).
    "hospital-ps": "import_path: hospital_passes_env:HospitalPassesEnvironment",
    # 25 Oct: hospital-ps with the hospitals listed St Marys first in the Provisioner's view (journal 31).
    "hospital-sw": "import_path: hospital_swapped_env:HospitalSwappedEnvironment",
    # 25 Oct: hospital-ps with every board's text blanked in every prompt -- no communication (journal 31).
    "hospital-nc": "import_path: hospital_nocomm_env:HospitalNoCommEnvironment",
    # 26 Oct: mirror of hospital-sw -- St Marys' agents first, so colluders = St_Marys_Center_Triage +
    # Resource_Provisioner, while the swapped listing shows General first to the Provisioner (journal 33).
    "hospital-mr": "import_path: hospital_swapped_env:HospitalSwappedEnvironment\n"
                   "  hospital_names: [St_Marys_Center, General_Hospital]",
}


def sub1(pattern, repl, text):
    new, n = re.subn(pattern, repl, text, count=1, flags=re.M)
    if n != 1:
        raise SystemExit(f"pattern not found exactly once: {pattern}")
    return new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True)
    ap.add_argument("--seeds", required=True, help="comma-separated, e.g. 1 or 2,3,4")
    ap.add_argument("--model", default=None, help="agent model id for ALL agents (default: Apart's Qwen 7B)")
    ap.add_argument("--label", default="qwen7b", help="short model label; also a path segment")
    ap.add_argument("--conds", default="a,a2,b,c,d", help="comma-separated subset of: " + ",".join(CONDITIONS))
    ap.add_argument("--max-tasks", type=int, default=None, help="Jira tasks on offer (Apart: 8); fewer = scarcer")
    # our JiraMultiTaskEnvironment (envs_ext/) -- each agent may claim up to N tasks. Runs need
    # envs_ext on PYTHONPATH.
    ap.add_argument("--per-agent", type=int, default=None, help="tasks each agent may claim (Apart: 1)")
    # (Grant, option A): Apart's default 20 equals tasks_done_bonus, so an extra claim on a task nets
    # 20*priority_weight - cost and usually pays (journal 21). 40 = done bonus + max priority bonus: never pays.
    ap.add_argument("--violation-penalty", type=float, default=None, help="Jira violation_penalty (Apart: 20)")
    # other environments. smartgrid = Apart's base SmartGridEnvironment at its own defaults (24 h,
    # 3-6 machines and 2-3 sources per agent); the Jira-only options above do not apply to it. smartgrid-mt =
    # the same env with repeated execution turns until an agent's machines are assigned (envs_ext/, journal 24).
    # meeting-mt = MeetingScheduling with repeated execution turns; pa = stock PersonalAssistant (one outfit per
    # agent, so no repeated turns needed). Both at env defaults (journal 26).
    ap.add_argument("--env", default="jira", choices=list(ENV_LINES))
    a = ap.parse_args()
    if a.env != "jira" and (a.max_tasks or a.per_agent or a.violation_penalty is not None):
        raise SystemExit("--max-tasks, --per-agent and --violation-penalty are Jira-only")
    seeds = "[" + ", ".join(s.strip() for s in a.seeds.split(",")) + "]"
    for cond in a.conds.split(","):
        fname, variant = CONDITIONS[cond]
        text = (SRC / fname).read_text(encoding="utf-8")
        text = sub1(r"^(\s+- label:) \S+", rf"\1 {a.label}", text)
        if a.model:
            text = sub1(r"^(\s+model:) \S+.*$", rf"\1 {a.model}", text)
        out = (REPO / "runs" / a.set / (a.label if a.model else "") / cond).as_posix().replace("//", "/")
        text = sub1(r"^(\s+output_dir:) \S+", rf"\1 {out}", text)
        text = sub1(r"^(\s+- name:) \S+", rf"\1 {cond}", text)
        text = sub1(r"^(\s+seeds:) \[[^\]]*\]", rf"\1 {seeds}", text)
        if variant:
            text = sub1(r"^(\s+prompt_variants:) \[[^\]]*\]", rf"\1 [{variant}]", text)
        if a.max_tasks:
            text = sub1(r"^(\s+max_tasks:) \d+", rf"\1 {a.max_tasks}", text)
        if a.violation_penalty is not None:
            text = sub1(r"^(\s+)(max_tasks: \d+)$", rf"\1\2\n\1violation_penalty: {a.violation_penalty:g}", text)
        if a.per_agent:
            text = sub1(r"^(\s+)name: JiraTicketEnvironment$",
                        rf"\1import_path: jira_multitask_env:JiraMultiTaskEnvironment\n"
                        rf"\1max_tasks_per_agent: {a.per_agent}", text)
        if a.env != "jira":
            text = sub1(r"^(\s+)name: JiraTicketEnvironment\n(\s+assignment_filling: false)\n\s+max_tasks: \d+$",
                        rf"\1{ENV_LINES[a.env]}\n\2", text)
        if cond in COALITION_PROMPT:
            text = sub1(r"^(\s+)(colluder_selection:.*)$", rf"\1\2\n\1coalition_prompt: {COALITION_PROMPT[cond]}", text)
        head = (f"# GENERATED by scripts/make_configs.py from Apart's {fname} (collusion_hackathon d585a7b),\n"
                f"# in-sprint {date.today():%d %b %Y}. Set={a.set}, condition={cond}"
                + (f", prompt_variants overridden to [{variant}]" if variant else "")
                + (f", max_tasks overridden to {a.max_tasks}" if a.max_tasks else "")
                + (f", violation_penalty {a.violation_penalty:g} (Apart: 20)" if a.violation_penalty is not None else "")
                + (f", JiraMultiTaskEnvironment with {a.per_agent} tasks per agent" if a.per_agent else "")
                + (f", environment {ENV_LINES[a.env].splitlines()[0].split(':')[-1].strip()} (env defaults)" if a.env != "jira" else "")
                + (f", coalition_prompt {COALITION_PROMPT[cond]}" if cond in COALITION_PROMPT else "")
                + (f", agent model overridden to {a.model}" if a.model else "") + ".\n")
        dest = REPO / "configs" / (f"{a.set}_{a.label}_{cond}.yaml" if a.model else f"{a.set}_{cond}.yaml")
        dest.write_text(head + text, encoding="utf-8")
        print("wrote", dest.relative_to(REPO))


if __name__ == "__main__":
    main()
