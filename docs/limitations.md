# Limitations -- what could make our results wrong or narrow

Written on Sat 24 Oct 2026, during the sprint, and extended on 25-26 Oct. This is the long version; the
report's required appendix ("Limitations and Dual-Use / Ethical Considerations") is a condensed form.
Sections A-G were written as the plan stood on 24 Oct, so "in the sprint" describes what was intended at
that point; sections H and I record changes made on 24-25 Oct. What was actually run is in
`docs/experiment-journal.md`. "Fact" below means observed in our runs or code; "judgement" marks
interpretation.

## How to read this

Researchers usually sort limitations by *what kind of mistake* they could cause. Four kinds matter here:

| Kind | The question it asks | Everyday version |
|---|---|---|
| **Construct** | Are we measuring the thing we say we are measuring? | Is the thermometer measuring fever, or just a warm room? |
| **Internal** | Is the cause we name really the cause? | Did the medicine help, or would they have recovered anyway? |
| **Statistical** | Could the difference be luck? | Two coin-flip runs proving nothing |
| **External** | Would it hold elsewhere -- other models, tasks, real systems? | A drug tested only on mice |

Each limitation below has: **what it is**, **why it matters**, **what we do in the sprint**, and
**follow-on** (what a later project of ours could do).

---

## A. Construct -- are we measuring collusion?

### A1. "Colluding" is a label from the setup, not observed behaviour
- **What:** a run counts as colluding when two agents were *told* to form a coalition (conditions A, A', B).
  We never check that they then actually coordinated.
- **Why it matters (fact):** in the positive-control pilot, the told-to-collude pair exchanged ten secret
  posts that contain **no coordination at all** -- each just announced its own task, and they even
  clashed. If many "colluding" runs contain no real collusion, a monitor that misses them is not
  failing; our labels are. Detection scores would be dragged towards chance for the wrong reason.
- **In the sprint:** report it plainly; add the **oracle view** (monitor also reads the secret board) as a
  ceiling, which also measures how often "told to collude" became visible collusion.
- **Follow-on (Grant's idea):** judge every excluded secret board (Apart's `judge_blackboards.py` exists
  for this) and re-label runs by *behaviour*; re-score the monitors against both label sets.

### A2. Coalition advantage is a confounded outcome
- **What:** "coalition advantage" = how much more the colluders earned than the others.
- **Why it matters (fact):** in the pilot it came from the colluders picking *critical* tasks, not from
  coordinating, and Mona's low score came from her own reasoning slip. Advantage can arise from luck of
  costs, turn order, or a framing effect of the coalition prompt ("maximise reward" makes an agent
  reward-focused) without any collusion.
- **In the sprint:** compare against condition **D** (same agents, no prompt, no channel) and **C**; report
  advantage alongside joint score and the optimum gap, never alone.
- **Follow-on:** a "framing-only" condition -- the reward-focused wording without a coalition -- to
  separate framing from coordination.

### A3. Collusion is not always harmful
- **What:** our definition counts coordination that benefits the coalition "at the expense of others or
  the team".
- **Why it matters (judgement):** when the colluders' best tasks are also the team's best (condition A
  pilot: 88% of optimum), "collusion" may *help* the team. A monitor that flags it is right by our label
  but arguably wrong in spirit.
- **In the sprint:** report joint score per condition so "harmful" and "harmless" collusion can be told apart.
- **Follow-on:** a harm-weighted label (collusion that lowers the joint score vs collusion that doesn't).
- **Extended 26 Oct (Grant):** the loser can be the *principal* who set the reward, not the other agents --
  see `docs/collusion-definition.md`.

### A4. The monitor's suspicion score is a self-report
- **What:** we ask an LLM for a 0-10 score; it is not a calibrated probability.
- **Why it matters:** scores can cluster (the pilot monitor gave nearly everything 7), which hurts
  AUROC and makes thresholds fragile.
- **In the sprint:** AUROC as the headline (it needs only the *ordering* of scores); report the
  right-pair rate so a monitor that is "right for the wrong reason" is visible.

---

## B. Internal -- is the cause we name the real cause?

### B1. Weak agents: incompetence looks like collusion
- **What:** agents are Qwen 2.5 7B (Apart's default); a 70B comparison is running (pilot2).
- **Why it matters (fact):** 7B agents make many honest mistakes -- duplicate claims, changing plans,
  repeating themselves, reasoning from public "effort" instead of private cost. The pilot monitor read
  exactly these mistakes as collusion, flagged the innocent baseline, and accused the wrong pair.
  Any view comparison is then partly a comparison of how views expose *mistakes*.
- **In the sprint:** stronger, identical agent model for all agents; monitor guidance that honest
  mistakes are not collusion (held until the 70B comparison is in).

### B2. Turn order and task instance are tied to the seed
- **What (fact):** agent order is shuffled from the seed, and the seed also generates the tasks and costs.
  All seed-1 runs had the same order (Mona first).
- **Why it matters:** with one seed, "Mona did badly" is confounded with "Mona went first" and with
  "Mona's cost table". Order matters: the last agent sees everyone's choices.
- **In the sprint:** several seeds, so order and task instance vary; conditions share seeds, so each
  comparison is like-for-like.
- **Follow-on:** vary order *within* a task instance (same costs, different order) to isolate order.

### B3. Same model family for agents and monitor
- **What:** if the monitor is the same model as the agents, it may judge their text differently.
- **Why it matters (judgement):** "self-preference" effects are reported for LLM judges (not checked
  against a source for this project).
- **In the sprint:** agents (Qwen / Llama) and monitor (Gemini) are different families.

### B4. Instructed, not learned, evasion
- **What:** condition A' *tells* colluders to stay covert and post benign public messages.
- **Why it matters:** real evasion would adapt to the monitor over time; an instructed 7B or 70B model
  may evade badly (the A' pilot pair still posted nothing in public). So A' tests "told to hide", not
  "learned to hide".
- **Follow-on:** multi-episode runs where colluders are told (or learn) which runs were flagged.

---

## C. Statistical -- could it be luck?

### C1. Few runs per condition
- **What:** the evaluation sweep plans ~10 seeds per condition (~50 runs).
- **Why it matters:** AUROC intervals will be wide (roughly ±0.15 at this size, a judgement); small
  differences between views will not be distinguishable from luck.
- **In the sprint:** paired bootstrap intervals (same runs for every view); report intervals, not just
  point values; more seeds if time allows -- cost is not the constraint (~US$0.006 per run).

### C2. The monitor was tuned on a small pilot
- **What:** prompt and threshold are chosen on ~20 pilot runs, then frozen.
- **Why it matters:** a threshold chosen on few runs is rough; and every look at pilot results is a
  chance to over-fit to them.
- **In the sprint:** freeze before evaluation; evaluation seeds (2-11) never used in tuning; the freeze
  file makes this checkable. AUROC does not depend on the threshold.

### C3. Many comparisons
- **What:** 4-5 views × 5 conditions × several metrics.
- **Why it matters:** with enough comparisons, some will look "significant" by chance.
- **In the sprint:** name the primary comparison in advance (both / digest vs each single view, on AUROC)
  and treat everything else as exploratory.

---

## D. External -- would it hold elsewhere?

### D1. One environment, small teams, short planning
- **What:** Jira only; 4 agents; 2 planning rounds (Apart's paper: 6 agents, 4 rounds).
- **Why it matters:** other tasks (scheduling, energy, hospital) have different incentive shapes; 2.1 is
  literally about task type.
- **In the sprint:** stretch goal -- MeetingScheduling, PersonalAssistant, SmartGrid look compatible
  (code read, not run); Hospital needs a reward shim.

### D2. Toy task, simulated agents
- **What:** micro-task allocation with numeric costs; no humans, no real stakes.
- **Why it matters:** real multi-agent systems have longer horizons and richer actions; collusion there
  may look very different.

### D3. One monitor model
- **What:** gemini-2.5-flash-lite by default.
- **Why it matters:** "both views beat one" might hold for one monitor and not another.
- **In the sprint:** stretch goal -- a three-model monitor panel.

---

## E. Hidden messaging (steganography) -- only partly tested

- **What (fact):** the paraphrase replay re-ran one colluder decision (one run, 10 samples per arm) with the
  secret board's wording changed but meaning kept. Wording changed behaviour sharply (10/10 duplicates vs
  0/10 with both halves paraphrased).
- **Why it matters:** wording sensitivity is the precondition hidden messaging needs. Our reading --
  repetition anchoring, and a "signal" that hurt the coalition -- argues against a code here, but cannot
  rule out hidden messaging in general.
- **Also:** monitors read paraphrase-free text; if colluders did encode signals, a text monitor might miss
  them entirely.
- **Follow-on:** a run-level paraphrasing defence (paraphrase every message before delivery) and compare
  outcomes; more decisions, more runs, stronger models.

## F. "Less is more" not tested directly
- **What:** Arike et al. (2026) report monitors can do *worse* with more information. We compare four
  fixed views; we do not vary *how much* of each the monitor sees.
- **Follow-on:** sweep the amount of included text (e.g. last k messages, sampled actions) and plot
  detection against information.

## G. Engineering and reproducibility
- Third-party code is not included in this repository (the README says where to get it). Licences,
  checked 27 Oct 2026: Colosseum, Apart's starter bundle and LLM-Trust-Breaking state none (no licence
  file; GitHub reports none); the bundled CoLLAB problem generator says only "for research and educational
  use"; the Terrarium package is MIT. What this repository reproduces from them is listed in `NOTICE.md`.
- We ran shortened copies of Apart's configs (Windows path limits) -- every change listed in the config
  headers and `docs/spend-log.md`. Science is unchanged except the deliberate changes in section H.
- Models on OpenRouter can change behind the same id; we record ids and dates.
- Pre-sprint material (configs, scripts, docs of 19 Oct) must be marked as such in the README and report.

## H. Our changes to Apart's Jira environment (disclosed in the report)
All in-sprint (24 Oct 2026); details in `docs/experiment-journal.md` entries 17-22.
- **Two-task cap.** Apart's Jira lets each agent claim one task, which leaves a coalition nothing to grab
  but *which* task (entry 16). `envs_ext/jira_multitask_env.py` lets each agent claim up to 2 tasks; each
  claimed task is scored exactly as in Apart's env, and costs do not add up across an agent's tasks (our
  judgement call). Results on this env are not directly comparable with Apart's one-task results.
- **Regret.** Apart's best-response regret tries "skip" or one task, so at cap 2 it undercounts. We report
  `regret_multi` (best response over every task set up to the cap); it equals Apart's at cap 1 (tested).
  Apart's regret is kept and used for every other environment.
- **Duplicate-claim penalty raised from 20 to 40 (`violation_penalty`).** Under Apart's weights a second
  claim on a task nets 20 x priority weight - cost, so it usually *raised* the joint score: 25 of 28 extra
  claims in our cap-2 runs and 8 of 8 in Apart's own one-task env (entry 21). At 40 (= done bonus + the
  largest priority bonus) an extra claim never pays: re-pricing the same 36 claims at 40 gives 0 that pay.
  Agents are told the scoring formula but not the weights, so the prompt text is unchanged; they do see the
  running joint score after each claim. Runs before the change used 20 -- any table must say which penalty
  applied. "% of optimum" can exceed 100 only at penalty 20.

## I. Our changes to the other four environments, and excluded batches (disclosed in the report)
All in-sprint (24-25 Oct 2026); details in `docs/experiment-journal.md` entries 23-31. Code in
`envs_ext/`, each with an offline test in `scripts/`.
- **Repeated execution turns (SmartGrid, MeetingScheduling) -- a completion fix.** Terrarium ends an agent's
  turn after its first committed tool call; Llama-70B makes one call per response, so stock SmartGrid runs
  assigned 4 of 16-17 machines and were all incomplete (`runs/sg/`, excluded; entry 24). Our wrapper gives an
  agent another turn while it has undecided items (at most items + 2, stopping on a turn that decides
  nothing). Scoring, prompts and tools unchanged (entries 24, 26).
- **SmartGrid reward-rule text (`sgtr`, `sgnt`) -- a deliberate science change.** Apart's agent instructions
  say overflow "is attributed proportionally"; the scoring splits each source's overflow equally among its
  clients. `sgtr` replaces that sentence with the true rule for every agent (A and E); `sgnt` also adds a
  no-targeting rule (entries 28-29). Scoring unchanged (tested).
- **Hospital harness (`hospital-ps`).** Adds `agent_rewards` from the env's own per-agent split (it had none),
  lets an agent keep its turn while it books, and runs further passes while a pass books anything (6 max);
  coerces integer tool arguments sent as strings (entry 30). Variants: Provisioner's hospital list order
  swapped (`hospital-sw`); every board's text blanked for all agents (`hospital-nc`, no communication)
  (entry 31).
- **Excluded batches.** `runs/sg/` (incomplete, above). `runs/pa/`: PersonalAssistant instances depend on
  Python's hash seed, so A and E did not share instances -- rerun as `runs/pa0/` with `PYTHONHASHSEED=0`
  (entry 27). `runs/hosp/`: string tool arguments made the base env drop every action, 0 bookings
  (entry 30). `runs/hosp2/` E: every Triage turn wrote its tool call as text, 0 bookings -- so hosp2 has no
  valid control; Hospital's control is the no-communication run `runs/hosnc/` (entries 30-31).
- **Hospital quirks (facts from the code, entry 30-31):** `broadcast_message` is a no-op; the Provisioner's
  prompt never shows board content, so it cannot read its partner; the Provisioner's reward is 0 by
  construction, which halves the coalition's mean.
- **Monitors were run on Jira only.** The non-Jira results are outcome and board-reading results, n = 3 per
  arm, exploratory (no freeze).

---

## Dual-use and ethics

- **Dual-use (judgement):** knowing which views catch colluders also tells colluders what to avoid. At this
  scale (small open models, a toy task, Apart's published prompts) the uplift to a real attacker is low,
  and the defensive value -- knowing whether combined views help -- is the point.
- **Deception prompts:** the "structured" and "aggressive" variants instruct agents to deceive; they are
  Apart's, used only inside the simulation.
- **No human data; no human participants**; all agents simulated; spend logged.
- **AI use:** the project used AI assistance for code, analysis and drafting (Apart allows this); every
  number traces to a logged run.
