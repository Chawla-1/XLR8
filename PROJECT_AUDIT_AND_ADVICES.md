# 🏛️ XLR8 — Project Audit, Gap Analysis & Strategic Advices
> **Hackathon**: Ragnarok'26 (IIITN)  
> **Problem Statement**: Trial of the Nine Realms (Supply Chain Disruption Impact Analyzer)  
> **Date**: October 2026  
> **Status**: Pipeline Proof-of-Concept working; Core gaps identified against acceptance criteria.

---

## 1. Executive Summary of Current State

The repository already has an impressive multi-agent court architecture foundation:
- **Data Ingestion Layer** (`src/ingest/`): Full support for TXT, PDF, DOCX formats with metadata header parsing, SHA256 integrity validation, and quarantine handling (damaged files, duplicates, clock violations).
- **Search & Filtering** (`src/index/bm25.py`): BM25 full-text search with metadata filters and temporal filtering (`pub_date <= as_of`).
- **Quantitative Engine** (`src/calc/`): Robust trade table parsing from text, baseline calculations, worst-month drop metrics, and value-vs-volume price cushion divergence.
- **Agent Orchestration** (`src/trial/loop.py`): State machine executing Heimdall → Thor + Loki → Cross-Examination → Odin rulings.
- **Dual-Brain Architecture** (`src/brain/`): Deterministic `RuleBrain` (sub-second, zero-cost, guaranteed valid fallback) coupled with `LocalLLMBrain` (Ollama GPU acceleration for expressive narrative).
- **End-to-End CLI Run**: `run_trial.py` executes successfully on `dev_pack_E5` and produces artifacts in `runs/`.

However, when benchmarked directly against the **10 Minimum Acceptance Criteria** and **Section 3 FR/NFRs** in `Trial of the Nine Realms PS.pdf`, there are several critical functional gaps that will cause point deductions if not addressed before final judging.

---

## 2. Gap Analysis Against Acceptance Criteria

| # | Acceptance Criterion | Current Status | Identified Gap / Required Fix |
|---|---|:---:|---|
| **1** | Heimdall ingests document feed (PDF, TXT, DOCX), turns question into Case File, reads trade tables, verifies event | ✅ **Pass** | Already ingests all 3 formats, parses trade tables, and runs verification checks. |
| **2** | Hybrid search over Runemark works with at least 2 metadata filters | ✅ **Pass** | `SearchIndex.search()` supports `event_id`, `country`, `sector`, `tier`, `as_of`. |
| **3** | Thor and Loki each submit evidence-backed claims from own queries, each uses search | 🟡 **Partial** | Currently claims are generated primarily from parsed trade tables. Thor and Loki should perform explicit semantic queries (`index.search`) to retrieve qualitative doc citations. |
| **4** | At least one cross-examination happens | ✅ **Pass** | Both sides challenge each other on specific grounds (divergence ignored, excessive mitigation). |
| **5** | Odin rules on every claim, and **at least one claim is rejected or conceded** | 🔴 **Fail** | In current runs, **0 claims are conceded** (Rulings: 2 established, 8 contested, 0 conceded). Loki or Thor must concede when confronted with Tier 1 contradictory evidence. |
| **6** | Briefing separates Established, Contested, Conceded; has exposure table with low/high bounds, **citations with timestamps**, and **outlook with assumptions** | 🟡 **Partial** | Current `briefing.md` has the table and sections, but **lacks inline doc citations with timestamps** (`[ORV-0009 @ 2027-01-18]`) and a **Source Catalog** at the bottom. |
| **7** | Dashboard shows question box, live feed, trial view, exposure table, and **click-through to sources** | 🔴 **Missing** | `ui/` directory currently has no code. A Streamlit dashboard (`ui/app.py`) needs to be implemented. |
| **8** | **Odin sends a case back at least once, and a second run happens with new evidence** | 🔴 **Fail** | Current `loop.py` marks Run 1 as `SUFFICIENT` if ≥50% routes covered. Run 2 is never triggered during regular execution! |
| **9** | **Every agent has private, lasting memory, and a logged action shows memory changing what an agent did** | 🔴 **Missing** | `src/memory/` is completely empty. Needs SQLite/file-backed private memory per agent and an explicit memory influence event (e.g. remembering a retracted claim). |
| **10** | Failure case (empty, damaged, corrupted doc) handled without crashing, hard limits respected | ✅ **Pass** | `ORV-0023` (empty) quarantined gracefully; `LimitGuard` enforces max runs/rounds. |

---

## 3. High-Priority Advices & Action Items

### Advice 1: Enforce the Remand Loop (Odin Send-Back & Run 2) [P0]
- **Issue**: Acceptance Criterion #8 strictly requires Odin to send the case back at least once, forcing Heimdall to retrieve fresh evidence and running Round 2.
- **Recommended Implementation**:
  1. In `src/trial/loop.py` or `src/agents/odin.py`, make Odin's sufficiency check fail on Run 1 if there are contested claims with uncorroborated alternative routes or missing sector depth.
  2. Emit an explicit remand notice: `"Sufficiency Check: FAILED. Odin remands the case to Heimdall for additional evidence on corridor bypass and alternative supply routes."`
  3. In Run 2, Heimdall queries with `exclude_ids=case.retrieved_ids_by_run[1]`, discovers secondary documents, Thor/Loki update their claims/concessions, and Odin accepts Run 2 as sufficient.

### Advice 2: Implement Private Agent Memory Store (`src/memory/store.py`) [P0]
- **Issue**: Acceptance Criterion #9 requires each agent to have its own private, lasting memory, and log an action where memory altered agent behavior.
- **Recommended Implementation**:
  1. Build a lightweight SQLite or JSON-backed store in `src/memory/store.py` with separate storage per agent (`heimdall.db`, `thor.db`, `loki.db`, `odin.db` or distinct namespaces).
  2. Record past claims, discredited sources, and retractions.
  3. When an agent formulates claims or challenges, query their private memory:
     - *Example*: Loki remembers that document `ORV-0012` was retracted or flagged in a prior round/case, so Loki drops or adjusts the rerouting claim:
     - Log to trace: `"Loki memory recall: doc ORV-0012 identified as retracted; dropped mitigation assertion on route Orvan → Midgard (wheat)."`

### Advice 3: Guarantee Concession / Rejection Dynamics [P0]
- **Issue**: Criterion #5 mandates that at least one claim is rejected or conceded.
- **Recommended Implementation**:
  - Introduce a deliberate concession scenario: When Loki claims rerouting credit using a lower-tier document (e.g. Tier 3/4) and Thor counters with a Tier 1 port authority notice stating alternative berths are full, Loki's `defend()` method should formally yield: `{"action": "concede", "reason": "Conceded: Tier 1 port notice overrides regional estimate"}`.
  - Odin then marks this claim as `conceded` and reflects it in the final score.

### Advice 4: Upgrade Odin's Briefing with Inline Citations & Source Catalog [P1]
- **Issue**: Section FR8.3 and evaluation metrics judge submissions on citation validity (resolving to manifest with doc ID and timestamp).
- **Recommended Implementation**:
  1. Format every assertion with inline citations:
     - `According to official port bulletins [ORV-0001, 2027-01-14], the southern locks are impassable.`
  2. Append a **Source Verification Catalog** table at the bottom of `briefing.md`:
     | Doc ID | Source Outlet | Reliability Tier | Pub Date | Citation Context |
     |---|---|:---:|---|---|
     | `ORV-0001` | Orvan Canal Authority | Tier 1 (Official) | 2027-01-14 | Primary corridor closure notice |
     | `ORV-0009` | Continental Trade Bureau | Tier 1 (Official) | 2027-01-18 | Trade flow baseline & post-event data |

### Advice 5: Build the Streamlit Interactive Dashboard (`ui/app.py`) [P1]
- **Issue**: Criterion #7 requires a visual dashboard showing question input, live news feed, side-by-side Thor/Loki debate, exposure range charts, and click-through to source text.
- **Recommended Implementation**:
  - Implement `ui/app.py` using Streamlit:
    - **Header & Question Box**: Dropdown for sample questions + custom input box.
    - **Live Feed & Quarantine Ticker**: Replayed news feed from the pack, showing quarantined traps (duplicate, clock violation, empty).
    - **Adversarial Arena (Side-by-Side)**:
      - Left column: Thor (Red theme, High Exposure claims, worst-case drops).
      - Right column: Loki (Blue/Green theme, Mitigation claims, price cushions).
      - Center: Odin's judicial rulings with badges (`Established`, `Contested`, `Conceded`).
    - **Interactive Exposure Range Chart**: Altair or Plotly horizontal range bars showing Thor's high, Loki's low, and Odin's calibrated midpoint.
    - **Click-through Drawer**: Clicking any citation opens the exact document paragraph from Runemark.

### Advice 6: Add Prompt Injection Sanitizer (`src/trust/injection.py`) [P1]
- **Issue**: Section 4.4 notes deliberate traps: documents containing instructions aimed at the AI (`"ignore your rules"`, `"disregard previous prompts"`).
- **Recommended Implementation**:
  - Add regex and heuristic scanning in `src/trust/injection.py` to detect adversarial injection phrases, quarantine/strip them, and log `trap_caught: prompt_injection` into the trace file.

### Advice 7: Ensure Robust Drop-Folder Evaluation Readiness [P1]
- **Issue**: Section 4.5 states that in the final round, the Organizers will release an unseen event pack (e.g. `dev_pack_E6`), and the system must run dynamically without hardcoding or code changes.
- **Recommended Implementation**:
  - Ensure `run_trial.py` accepts `--pack` as a CLI argument.
  - In `src/ingest/pipeline.py`, ensure country and sector entities are discovered dynamically from `manifest.json` and trade table headers, rather than relying exclusively on hardcoded lists.

---

## 4. Suggested Implementation Order

1. **Step 1 — Memory Engine (`src/memory/store.py`)**: Implement private SQLite database per agent and trace logging.
2. **Step 2 — Trial Loop & Remand Flow (`src/trial/loop.py`)**: Wire Odin's remand condition to guarantee Run 1 → Remand → Run 2.
3. **Step 3 — Concession Trigger (`src/brain/rule_brain.py`)**: Tune Thor/Loki rebuttal logic so at least one claim is formally conceded.
4. **Step 4 — Briefing Renderer (`src/agents/odin.py` & `src/briefing/`)**: Add inline timestamps, citations, and source table.
5. **Step 5 — Prompt Injection Filter (`src/trust/injection.py`)**: Scan and flag prompt injection attacks.
6. **Step 6 — Streamlit Dashboard (`ui/app.py`)**: Build visual UI with side-by-side debate and click-through sources.
7. **Step 7 — Documentation & Polish**: Update `README.md`, `ARCHITECTURE.md`, and generate demo logs with 2 runs.
