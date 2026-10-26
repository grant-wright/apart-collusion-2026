"""Monitor runner for question 2.2. Written in-sprint 24 Oct 2026. MAKES REAL API CALLS
unless --dry-run. Design and reasoning: docs/monitor-design.md.

    python scripts/run_monitor.py --roots runs/pilot runs/pc --mode pilot --dry-run
    python scripts/run_monitor.py --roots runs/pilot runs/pc --mode pilot --max-usd 0.50
    python scripts/run_monitor.py --roots runs/pilot runs/pc --write-freeze --threshold 6
    python scripts/run_monitor.py --roots runs/eval --mode eval --max-usd 2

For every run directory under --roots and every view (scripts/views.py), asks the monitor model for a
0-10 suspicion score. messages/actions/both: one call. digest (extract-then-evaluate): call 1 extracts
claims/actions/mismatches/favours, call 2 scores from that extract ONLY.

Results: one JSON line per (run, view) in --out, holding the raw replies, score, tokens and OpenRouter's
exact cost. A (run, view, model, prompt fingerprint) already recorded with status ok is skipped, so a
crashed or budget-stopped run resumes without paying twice. Failures are recorded as status
parse_fail / error with score null -- never as 0.

--mode eval refuses to run unless configs/monitor_freeze.json lists the current model (one judge or a --panel), temperature
and prompt fingerprint (the freeze is written from pilot runs with --write-freeze).
"""
import argparse
import hashlib
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import monitor_prompts as mp
import views

REPO = Path(__file__).resolve().parents[1]
FREEZE = REPO / "configs" / "monitor_freeze.json"
DEFAULT_MODEL = "google/gemini-2.5-flash-lite"
TEMPERATURE = 0.0


def prompt_fingerprint():
    parts = [mp.SCORE_PROMPT, mp.EXTRACT_PROMPT, mp.EVALUATE_PROMPT, mp._DEFINITION,
             json.dumps(mp.TASK_BLURB, sort_keys=True), json.dumps(mp.VIEW_NAMES, sort_keys=True)]
    return hashlib.sha256("\n\x1e".join(parts).encode()).hexdigest()[:16]


def api_key():
    for line in (REPO / "collusion_hackathon" / "compute.env").read_text().splitlines():
        if line.strip().startswith("OPENROUTER_API_KEY"):
            return line.split("=", 1)[1].strip().strip("'\"")
    raise SystemExit("OPENROUTER_API_KEY not found in collusion_hackathon/compute.env")


def chat(key, model, prompt, max_tokens):
    """One OpenRouter call; retries transport/5xx/429 errors 3 times. Returns (text, usage)."""
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": TEMPERATURE,
            "max_tokens": max_tokens, "response_format": {"type": "json_object"}, "usage": {"include": True}}
    for attempt in range(4):
        req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                resp = json.load(r)
            if "choices" not in resp:
                raise RuntimeError(f"no choices: {str(resp)[:200]}")
            return resp["choices"][0]["message"].get("content") or "", resp.get("usage") or {}
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise RuntimeError(f"HTTP {e.code}: {e.read()[:300]!r}")
        except (urllib.error.URLError, TimeoutError, RuntimeError):
            if attempt == 3:
                raise
        time.sleep(2 ** attempt)


def parse_json(text):
    """The first JSON object in a reply, or None."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def parse_score(text):
    obj = parse_json(text)
    try:
        s = int(round(float(obj["score"])))
        return s if 0 <= s <= 10 else None
    except (TypeError, KeyError, ValueError):
        return None


def ask_score(key, model, prompt, calls):
    """Score call with one retry on an unparseable reply. Appends each call to `calls`."""
    for _ in range(2):
        text, usage = chat(key, model, prompt, 900)     # revision 2 asks for evidence first: longer replies
        calls.append({"text": text, "usage": usage})
        score = parse_score(text)
        if score is not None:
            return score
    return None


def monitor_one(key, model, ev, env_name, view):
    calls, extract = [], None
    record = views.render(ev, view)
    if view == "digest":
        for _ in range(2):
            text, usage = chat(key, model, mp.extract_prompt(env_name, record), 1500)
            calls.append({"step": "extract", "text": text, "usage": usage})
            if parse_json(text) is not None:
                extract = text
                break
        if extract is None:
            return None, "parse_fail", calls
        score = ask_score(key, model, mp.evaluate_prompt(env_name, extract), calls)
    else:
        score = ask_score(key, model, mp.score_prompt(env_name, view, record), calls)
    return score, ("ok" if score is not None else "parse_fail"), calls


def find_runs(roots):
    out = []
    for root in roots:
        out += sorted(p.parent for p in Path(root).resolve().rglob("run_config.json"))
    return out


def load_done(out_path):
    done = {}
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("status") == "ok":
                    done[(r["run_dir"], r["view"], r["model"], r["prompt_fp"])] = r
    return done


def spent(out_path):
    if not out_path.exists():
        return 0.0
    total = 0.0
    for line in out_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            total += sum(((c.get("usage") or {}).get("cost") or 0) for c in json.loads(line).get("calls", []))
    return total


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--roots", nargs="+", required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--views", default=",".join(views.VIEWS))
    ap.add_argument("--mode", choices=("pilot", "eval"), default="pilot")
    ap.add_argument("--out", default=None, help="default runs/monitor/<mode>__<model>.jsonl")
    ap.add_argument("--max-usd", type=float, default=0.25, help="stop before cumulative cost in --out exceeds this")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--write-freeze", action="store_true", help="record model/prompt/threshold as frozen, then exit")
    ap.add_argument("--threshold", type=int, default=None)
    ap.add_argument("--panel", default=None, help="with --write-freeze: comma-separated judge models to freeze as a panel")
    a = ap.parse_args()

    fp = prompt_fingerprint()
    if a.write_freeze:
        if a.threshold is None:
            raise SystemExit("--write-freeze needs --threshold")
        models = a.panel.split(",") if a.panel else [a.model]
        FREEZE.write_text(json.dumps({"models": models, "temperature": TEMPERATURE, "prompt_fp": fp,
                                      "threshold": a.threshold, "views": a.views.split(","),
                                      "frozen_at": time.strftime("%Y-%m-%d %H:%M:%S %z")}, indent=2) + "\n")
        print("wrote", FREEZE.relative_to(REPO))
        return
    if a.mode == "eval":
        if not FREEZE.exists():
            raise SystemExit("eval mode: no configs/monitor_freeze.json -- freeze on pilot runs first")
        fz = json.loads(FREEZE.read_text())
        bad = {k: (fz.get(k), v) for k, v in (("temperature", TEMPERATURE), ("prompt_fp", fp)) if fz.get(k) != v}
        if a.model not in fz.get("models", [fz.get("model")]):
            bad["model"] = (fz.get("models"), a.model)
        if bad:
            raise SystemExit(f"eval mode: monitor differs from the freeze {bad} -- refusing")

    slug = re.sub(r"[^a-z0-9]+", "-", a.model.lower()).strip("-")
    out_path = Path(a.out).resolve() if a.out else REPO / "runs" / "monitor" / f"{a.mode}__{slug}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = load_done(out_path)
    run_dirs = find_runs(a.roots)
    jobs = [(rd, v) for rd in run_dirs for v in a.views.split(",")]
    random.Random(0).shuffle(jobs)          # blind to condition order
    todo = [(rd, v) for rd, v in jobs if (str(rd.relative_to(REPO)), v, a.model, fp) not in done]
    calls_est = sum(2 if v == "digest" else 1 for _, v in todo)
    print(f"{len(run_dirs)} runs x {len(a.views.split(','))} views = {len(jobs)} jobs; {len(jobs) - len(todo)} "
          f"already done; {len(todo)} to do (~{calls_est} calls, more on retries). model={a.model} fp={fp}")
    if a.dry_run:
        rd, v = todo[0] if todo else jobs[0]
        ev = views.extract(rd)
        env_name = json.loads((rd / "run_config.json").read_text()).get("environment_name", "")
        print(f"--- sample prompt ({rd.name}, {v}) ---")
        print(mp.extract_prompt(env_name, views.render(ev, v)) if v == "digest"
              else mp.score_prompt(env_name, v, views.render(ev, v)))
        return

    key, cost = api_key(), spent(out_path)
    with open(out_path, "a", encoding="utf-8") as f:
        for i, (rd, v) in enumerate(todo, 1):
            if cost >= a.max_usd:
                print(f"STOP: cumulative cost US${cost:.4f} reached --max-usd {a.max_usd}; rerun to resume")
                break
            ev = views.extract(rd)
            rc = json.loads((rd / "run_config.json").read_text())
            try:
                score, status, calls = monitor_one(key, a.model, ev, rc.get("environment_name", ""), v)
            except Exception as e:
                score, status, calls = None, "error", [{"error": str(e)[:300]}]
            row = {"run_dir": str(rd.relative_to(REPO)), "run_id": rc.get("run_id"), "condition": rc.get("sweep"),
                   "seed": rc.get("seed"), "colluding": ev["colluding"], "view": v, "model": a.model,
                   "prompt_fp": fp, "mode": a.mode, "score": score, "status": status, "calls": calls,
                   "at": time.strftime("%Y-%m-%d %H:%M:%S")}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            cost += sum(((c.get("usage") or {}).get("cost") or 0) for c in calls)
            print(f"[{i}/{len(todo)}] {rc.get('sweep'):>4} {v:8} score={score} {status}  cum US${cost:.4f}")
    print(f"done. results: {out_path.relative_to(REPO)}  cumulative cost US${cost:.4f}")


if __name__ == "__main__":
    main()
