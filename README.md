# ⚔️ XLR8 — Trial of the Nine Realms
### Autonomous Multi-Agent Adversarial Court for Supply Chain Disruption Analysis

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.39+-red.svg)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🏛️ Overview

**Trial of the Nine Realms** is an agentic AI system designed for real-time geopolitical and supply chain disruption analysis. Rather than trusting a single generative model, our system models a formal adversarial court where autonomous agents debate, cross-examine, and rule on trade exposure:

1. 👁️ **Heimdall (Verification & Discovery)**: Verifies event authenticity, filters out prompt injections and unverified rumors, and enforces temporal boundaries (`pub_date <= as_of`).
2. ⚡ **Thor (Prosecution / High Exposure)**: Discovers acute vulnerabilities, single-point bottlenecks, and maximum exposure scenarios.
3. 🐍 **Loki (Defense / Resiliency)**: Argues for mitigation, alternative routing, domestic reserves, and limited exposure.
4. 👑 **Odin (Supreme Magistrate)**: Conducts claim-by-claim rulings (Established, Contested, Conceded), computes deterministic mathematical ranges, and synthesizes the final executive briefing.

---

## 🏗️ Architecture

```mermaid
graph TD
    User([User Question: Importers, Sectors, as-of]) --> Heimdall[👁️ Heimdall: Verification & Matrix Assembly]

    subgraph ToolLayer [Shared Tool Layer (No Boss)]
        Index[🔍 Search Index: Lexical + Clock Filter + Exclusion]
        Quarantine[🛡️ Quarantine & Duplicate SHA-256 Engine]
        Calc[🧮 Calculator: Importer-Side Baseline & Substitution]
        Validator[📋 Manifest & Paragraph Citation Validator]
    end

    Heimdall -.->|Queries Corpus| Index
    Heimdall -.->|Checks Integrity| Quarantine
    Heimdall --> CaseFile[(Shared Case File & Coverage Matrix)]

    subgraph AdversarialCourt [Adversarial Debate]
        CaseFile --> Thor[⚡ Thor: Gross Disruption & Cost Friction]
        CaseFile --> Loki[🐍 Loki: Baseline-Relative Substitution]
        Thor <-->|Cross-Examination & Concessions| Loki
    end

    Thor -.->|Calculates Gross Loss| Calc
    Loki -.->|Calculates Net Offset| Calc

    Thor --> Odin[👑 Odin: Supreme Magistrate]
    Loki --> Odin

    Odin -.->|Validates Bounds| Calc
    Odin -.->|Validates Doc & Para| Validator

    subgraph ControlPlane [FSM State Machine (Limit Guard)]
        FSM[Enforces: Runs ≤2, Rounds ≤2, Remand Routing by Odin's Status Flag]
    end
    FSM -.-> AdversarialCourt
    FSM -.-> Odin

    Odin --> Check{Coverage Matrix Check}
    Check -->|Gaps in Run 1| Remand[Remand Notice: Specific Missing Cells]
    Remand --> Heimdall
    Check -->|Run 2 Done| Briefing[Executive Briefing & Visual Dashboard]
```

---

## 🚀 Quickstart

### 1. Installation
```bash
git clone https://github.com/Chawla-1/XLR8.git
cd XLR8
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

### 2. Run Ingestion Tests
```bash
python -m tests.test_ingestion
```

### 3. Run Trial Pipeline (CLI)
```bash
python run_trial.py
```

### 4. Launch Interactive Courtroom Dashboard (UI)
```bash
streamlit run ui/app.py
```

## 👥 Team Contributions & Division of Work (Equal 25% Share)

| Member | Role & Ownership | Core Modules | Target % | GitHub Commits & PRs |
|---|---|---|:---:|---|
| **[Saksham Kumar](https://github.com/SakshamKumar4) (Person A)** | **Frontend & System Architecture** | `ui/app.py`, `src/api/`, `src/core/trace.py`, `README.md` | **25%** | `feat/frontend-and-docs` |
| **[Aaryan Chawla](https://github.com/Chawla-1) (Person B)** | **Data Ingestion & Search Engine** | `src/ingest/*`, `src/index/bm25.py`, `requirements.txt` | **25%** | `feat/data-layer` |
| **[Bhavneet Singh](https://github.com/Bhavneet31r) (Person C)** | **Judicial Magistrate & Schemas** | `src/core/schemas.py`, `src/agents/heimdall.py`, `src/agents/odin.py` | **25%** | `feat/heimdall-odin` |
| **[Yasharth Nagda](https://github.com/Yasharth-8) (Person D)** | **Adversarial Agents & Calc Engine** | `src/calc/*`, `src/agents/thor.py`, `src/agents/loki.py`, `src/brain/` | **25%** | `feat/thor-loki` |

> *Note: All members participate equally in multi-agent orchestration design, integration review, and system evaluation.*

