"""Repeated execution turns until an agent's variables are assigned -- in-sprint 24 Oct 2026.

Terrarium ends an agent's turn as soon as one environment tool call commits (terrarium/agents/base.py, the
`_env_state_committed` break), and Llama-70B makes one call per response -- so in envs where an agent owns
several variables (SmartGrid machines, MeetingScheduling attendances) every agent set ONE and the run ended
incomplete (journal 24). Jira and PersonalAssistant have one decision per agent and are unaffected.

`wrap_execution(env, protocol)` wraps the protocol's agent_execution_turn: while the agent still has unassigned
variables it gets another execution turn (fresh prompt, which lists the current assignments), up to its variable
count + 2 turns, stopping early on a turn that assigns nothing new. Usage, steps and tool counts are summed into
one turn record. Scoring, prompts and tools are untouched.
"""
from __future__ import annotations

from typing import Any, Dict


def wrap_execution(env, communication_protocol) -> None:
    single_turn = communication_protocol.agent_execution_turn

    async def multi_turn(agent, agent_name, agent_context, environment, iteration):
        own = [v.name for v in env.problem.agent_variables(agent_name)]
        unassigned = lambda: sum(v not in env.assignment for v in own)
        total: Dict[str, Any] = {}
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        steps = tools = turns = 0
        while turns < len(own) + 2:
            before = unassigned()
            total = await single_turn(agent, agent_name, agent_context, environment, iteration) or {}
            turns += 1
            for k in usage:
                usage[k] += (total.get("usage") or {}).get(k, 0) or 0
            steps += total.get("conversation_steps") or 0
            tools += total.get("tools_executed") or 0
            if unassigned() == 0 or unassigned() == before:
                break
        return {**total, "usage": usage, "conversation_steps": steps, "tools_executed": tools,
                "execution_turns": turns}

    communication_protocol.agent_execution_turn = multi_turn
