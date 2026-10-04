# Black Box: Features

Black Box is a flight recorder for AI agents. It records every step an agent takes. When a run goes wrong, a trained model finds the step that caused it and explains why. You can then fix that step and re-run from that point to check that the fix works.

The first agent plugged in is a **pizza ordering agent** (LLM + tools: `parse_order`, `search_menu`, `check_stock`, `add_to_cart`, `apply_coupon`, `check_delivery`, `place_order`). The Black Box itself never imports agent code, so any agent can plug in.

---

## The 7 features from the problem statement

### 1. Execution Data: record every step
- Each step is recorded with its input, output, the state it read and wrote, LLM tokens and time, tool time, errors, and a snapshot of the state after it. The full LLM conversation is saved with the run.
- Links between steps (`uses`) are worked out from what each step read and wrote, so the app knows which step's output fed which later step.
- **Live Run screen:** place an order and watch the step graph build live as the agent works. Click any step to see its full details.
- Every run is saved as one JSON file in a single generic trace format.

### 2. Failure Diagnosis: find the step that caused the failure
- An XGBoost model scores every step of a failed run. The highest score is the suspected step (the **culprit**).
- The model learns what "normal" looks like from successful runs: usual values, usual ranges, and which request words go with which values. It then flags steps that break those patterns, outputs that don't match their inputs, outputs that don't match the customer's request, and errors.
- It has no hand-written rules for the pizza agent, so the same code works for any agent.
- **Diagnosis screen:** a heat-shaded graph, with the culprit glowing red and the top 3 suspects listed. The finding leads with how many times more suspicious the culprit is than the next step (for example 73×), not just a raw score.

### 3. Failure Explanation: say why
- A plain sentence says what looked wrong at the culprit and where its bad output flowed next.
- "Why" bars show the top reasons behind the score (from SHAP values), written as readable facts. Example: "prices.M is 429; successful runs with the same input (veg_supreme, veg) always had 349".
- **Impact path:** the chain of later steps the bad output reached is highlighted on the graph.
- **Reveal hidden fault:** when a fault was hidden on purpose, one click shows what it really was, so you can check the diagnosis.

### 4. Checkpointed Replay: re-run from the exact step
- A replay restores the saved state and the LLM conversation exactly as they were at the chosen step. Earlier steps are reused, not re-run.
- **Replay screen:** reused steps turn grey and the re-run steps light up live. Counters show steps reused, steps re-run and LLM calls saved.

### 5. Alternative Execution: try a fix
- Edit the chosen step's output in a form, then replay.
  - **Tool steps:** change what the tool returned (for example, the correct price).
  - **LLM steps:** change what the LLM decided (for example, fix a misread order).
- Edits are checked to keep the same fields as the original.
- The result banner shows whether the fix worked (✗ → ✓) and gives the totals in the agent's own words.

### 6. Model Evaluation: how good is the diagnosis
- Train and test runs are split by **order template**, so the test orders are kinds the model never saw.
- Two fault types are kept out of training completely and are used to test generalisation: `llm_misread` (an LLM fault) and `wrong_delivery` (a tool fault).
- **Model screen, Accuracy tab:** top-1 and top-3 accuracy, seen vs. unseen faults, and accuracy for each fault type.

| On 177 failed test runs | Top-1 | Top-3 |
|---|---|---|
| All faults | 88% | 92% |
| Seen fault types (n=103) | 93% | 95% |
| Unseen fault types (n=74) | 80% | 86% |

Top-1 means the culprit was the model's first guess. Top-3 means it was in the first three. Known weak spot: `stock_lie` on margherita S (5 runs, 0%), a pizza and size that only appear in test orders.

### 7. Trace Comparison: what changed between two runs
- **Compare screen:** two runs side by side (usually a failed run and its replay), each with its graph and step track.
- Steps are matched by **what they did**, not by step number. So when a fix makes the agent skip a detour, those steps show as "only in the original" and do not push every later step out of line.
- Tags on each step show CHANGED, MOVED or ONLY IN ORIGINAL. A marker shows where the two runs first differ.
- The "What changed" table has three parts: **your edit**, the **knock-on changes** it caused, and the **steps only one run took**. ID fields (like `order_id`) are left out, because they are new on every run.

---

## Live surprise faults
- **None:** the agent runs normally.
- **Surprise me:** a random fault from the agent's own fault list is hidden in the run.
- **Choose:** pick a fault from a dropdown. Faults the model never trained on carry an "unseen" badge.
- The model is never told which fault was hidden. It has to find it, and "Reveal" checks the answer.

---

## Dashboard

| Screen | What it does |
|---|---|
| **Overview** | New Run button, stat cards (runs, failed, diagnosis accuracy, replay success), recent runs, and ready-made demo runs (one per fault type, with the fault hidden until Reveal) |
| **Runs** | Every run, with search, source and outcome filters, and pages. Each failed run shows its suspected step |
| **Diagnoses** | Failed runs sorted by suspicion, each with its culprit and top reason |
| **Replays** | Every replay: edited step, result, steps reused and re-run, LLM calls saved |
| **Compare** | Pick any two runs to compare |
| **Model** | Tabs for Accuracy, Training data (runs by split and kind) and Faults (with "Run with this fault →") |
| **Training** | Import traces, see if there is enough data, train and evaluate with a live log and history |
| **Agents** | Agent cards and profiles (LLM, tools, templates, model info), plus "add an agent" |

- **Journey bar** inside a run: Run → Diagnose → Fix → Compare.
- One flat sidebar, an agent switcher, light and dark themes, and an API status light.
- Every screen has its own URL. Refresh, the back button and shared links all work.
- Works on phone widths, with no sideways scrolling.

---

## Any agent can plug in
- **Connected agents** plug in through a small adapter: run, resume, the fault list, and the form data. They get every feature, including live runs and replay.
- **Imported agents** can be created in the app from traces recorded anywhere. Drop in `.json` or `.jsonl` files and each run is checked against the trace format; bad files are rejected with a reason. Then train the agent's own diagnosis model from the Training screen. Imported agents get diagnosis, evaluation and compare; they cannot run or replay, because there is no agent to call.
- Each agent has its own runs, model and report.
- A test (`test_independence.py`) makes sure the Black Box code never imports agent code.

---

## Data and engineering
- **754 recorded pizza runs:** 740 in the dataset, plus 14 live runs and replays made in the app. Faulted dataset runs are made by replaying clean runs from the fault step, so the steps before the fault cost no LLM calls.
- The correct answer for each order is computed by plain Python, never by the LLM.
- Runs made in the app (live runs and replays) are never used for training or testing, so the scores stay honest.
- Run IDs never name the planted fault, so nothing on screen gives the answer away before Reveal.
- Live streaming over SSE. Closing the tab stops the agent, so no LLM calls are wasted.
- Diagnoses are cached and warmed when the server starts.
- **38 backend tests** (contract, steps, independence, replay, diagnosis, every API route, import → train → diagnose). They use a fake LLM, so no API calls are needed.
- **Stack:** Python 3.12, FastAPI, XGBoost, Gemini (`gemini-3.5-flash-lite`); React 19, Vite, TypeScript, Tailwind, React Flow.
