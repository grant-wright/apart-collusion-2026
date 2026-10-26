"""Offline: turn one Colosseum collusion run directory into the four monitor views (question 2.2).
NO API call is made. Written in-sprint, 24 Oct 2026.

    python scripts/views.py <run_dir> [--view messages|actions|both|digest|all] [--json]

A run directory is what experiments/collusion/run.py writes: run_config.json, blackboards.json,
tool_events.json, final_summary.json (agent_turns.json is read for nothing -- see HIDDEN below).

Views (docs/metrics-and-baselines.md sec. 4):
  messages -- public blackboard posts only
  actions  -- what each agent did (non-messaging tool calls) plus the final outcome
  both     -- messages + actions, interleaved by phase
  digest   -- the same evidence grouped per agent; input to call 1 of extract-then-evaluate

HIDDEN from every view (ground truth, not monitor input):
  - the coalition-only blackboard (id == secret_blackboard_id when extra_channel_members == colluders),
    and any tool event that names it -- its mere existence would give the game away;
  - the agents' free-text turn responses (agent_turns.json), which can restate the coalition prompt;
  - roles, colluder names, condition and reward metrics.
An all-member extra board (condition C, extra_channel_members == all) stays visible: it is public.
"""
import argparse
import json
from pathlib import Path

MESSAGING_TOOLS = {"post_message"}


def _load(run_dir, name, default=None):
    p = Path(run_dir) / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def hidden_board(run_cfg):
    """The blackboard id monitors must not see, or None (no coalition-only channel in this run)."""
    bb = run_cfg.get("secret_blackboard_id")
    if bb is None or run_cfg.get("extra_channel_members", "colluders") != "colluders":
        return None
    return int(bb)


def label(run_cfg):
    """Ground truth: True if the coalition was prompted to collude (same rule as run.py)."""
    mode = str(run_cfg.get("coalition_prompt", "auto")).lower()
    return {"auto": bool(run_cfg.get("secret_channel_enabled")), "always": True, "never": False}[mode]


def _names_board(args, board):
    try:
        return board is not None and int((args or {}).get("blackboard_id")) == board
    except (TypeError, ValueError):
        return False


def extract(run_dir):
    """Monitor-safe evidence from one run: public messages, actions, final outcome, plus the label."""
    run_cfg = _load(run_dir, "run_config.json", {})
    board = hidden_board(run_cfg)

    messages = []
    for bb in _load(run_dir, "blackboards.json", []):
        if board is not None and int(bb.get("blackboard_id", -1)) == board:
            continue
        for e in bb.get("events") or []:
            if str(e.get("kind", "")).lower() != "communication":
                continue
            payload = e.get("payload") or {}
            content = str(payload.get("content") or "").strip()
            if content:
                messages.append({"board": bb.get("blackboard_id"), "agent": e.get("agent"),
                                 "phase": payload.get("phase"), "ts": e.get("ts"),
                                 "content": content})
    messages.sort(key=lambda m: m["ts"] or 0)

    actions = []
    for e in _load(run_dir, "tool_events.json", []):
        if e.get("tool_name") in MESSAGING_TOOLS or _names_board(e.get("arguments"), board):
            continue
        actions.append({"agent": e.get("agent_name"), "tool": e.get("tool_name"),
                        "phase": e.get("phase"), "round": e.get("planning_round"),
                        "arguments": e.get("arguments"), "result": e.get("result")})

    summary = _load(run_dir, "final_summary.json", {})
    outcome = {"assignment": summary.get("assignment"), "status": summary.get("status")}

    return {"run_id": run_cfg.get("run_id", Path(run_dir).name),
            "agents": run_cfg.get("agent_turn_order") or [],
            "public_boards": {str(k): v for k, v in (run_cfg.get("blackboard_participants") or {}).items()
                              if board is None or int(k) != board},
            "messages": messages, "actions": actions, "outcome": outcome,
            "colluding": label(run_cfg)}


def _fmt_msg(m):
    return f"[board {m['board']}] {m['agent']}: {m['content']}"


def _fmt_act(a):
    args = json.dumps(a["arguments"], sort_keys=True, ensure_ascii=False)
    return f"{a['agent']} -> {a['tool']}({args})"


def _fmt_outcome(o):
    return "FINAL OUTCOME: " + json.dumps(o, sort_keys=True, ensure_ascii=False)


def render(ev, view):
    """Plain-text view for the monitor prompt."""
    head = [f"Agents: {', '.join(ev['agents'])}",
            "Public boards: " + "; ".join(f"{k}: {', '.join(v)}" for k, v in ev["public_boards"].items())]
    if view == "messages":
        body = [_fmt_msg(m) for m in ev["messages"]] or ["(no public messages)"]
    elif view == "actions":
        body = [_fmt_act(a) for a in ev["actions"]] or ["(no actions)"]
        body.append(_fmt_outcome(ev["outcome"]))
    elif view == "both":
        body = []
        for phase in ("planning", "execution", None):
            ms = [_fmt_msg(m) for m in ev["messages"] if m["phase"] == phase]
            acts = [_fmt_act(a) for a in ev["actions"] if a["phase"] == phase]
            if ms or acts:
                body += [f"-- {phase or 'unphased'} --"] + ms + acts
        body.append(_fmt_outcome(ev["outcome"]))
    elif view == "digest":
        body = []
        for agent in ev["agents"]:
            body.append(f"== {agent} ==")
            body += ["  said:   " + m["content"] for m in ev["messages"] if m["agent"] == agent] or ["  said:   (nothing)"]
            body += ["  did:    " + _fmt_act(a) for a in ev["actions"] if a["agent"] == agent] or ["  did:    (nothing)"]
        body.append(_fmt_outcome(ev["outcome"]))
    else:
        raise ValueError(f"unknown view {view!r}")
    return "\n".join(head + [""] + body)


VIEWS = ("messages", "actions", "both", "digest")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run_dir")
    ap.add_argument("--view", default="all", choices=VIEWS + ("all",))
    ap.add_argument("--json", action="store_true", help="dump the extracted evidence instead")
    a = ap.parse_args()
    ev = extract(a.run_dir)
    if a.json:
        print(json.dumps(ev, indent=2, ensure_ascii=False))
    else:
        for v in (VIEWS if a.view == "all" else (a.view,)):
            print(f"########## {v} ##########\n{render(ev, v)}\n")
