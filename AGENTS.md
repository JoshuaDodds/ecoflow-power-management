# AGENTS: Enterprise Project Guidelines

> **Purpose:** This file defines the global operational standards for both human developers and AI agents. It ensures that all work—regardless of the specific project—is tracked, documented, and executed with high-level reliability and transparency.

---

## 🤖 AI Agent Workflow & Jira Integration

All AI agents are granted administrative access to the relevant Jira project and are expected to manage the ticket lifecycle autonomously.

### 1. Ticket Discovery & Lifecycle
* **Regex Detection:** Detect Jira keys (e.g., `PROJ-123`) using `\b[A-Z][A-Z0-9]+-\d+\b`.
* **Initialization:** If a key is found, immediately:
    1. Transition to **In Progress**.
    2. Assign to self and comment "Agent started work."
    3. Update the title/description to a technical specification.
* **Creation:** If no key exists, create a new issue in the current active sprint.
* **Completion:** On the final commit, transition to **In Review**. Post a summary including testing steps for human verification. **Do not move to Done.**

### 2. Branching & Commit Policy
* **Naming:** All branches and PRs must be prefixed with the Jira key (e.g., `PROJ-123-feature-slug`).
* **Smart Commits:** Every commit must use the following format:
    `git commit -m "<KEY> <summary> #comment <detail> #time <duration> #transition <status>"`
* **Time Tracking:** Start a high-resolution timer before any work begins. Log actual wall-clock time rounded to the nearest minute. Redact PAT values in logs.

---

## 🏗 Engineering & Implementation Rules

### 1. Architecture & Design
* **Module Boundaries:** Respect encapsulation. Use explicit APIs for cross-component communication.
* **Non-Blocking IO:** Offload heavy CPU/IO tasks to background threads or processes.
* **Idempotency:** Prefer operations that can safely be retried (e.g., write-then-rename for file operations).
* **Subprocesses:** Include robust respawn logic, cleanup handlers, and failure telemetry for external binaries.

### 2. Code Quality (Python)
* **Typing:** Use type hints consistently for all new signatures.
* **Exceptions:** Never use broad `except:` blocks. Log all caught exceptions with context.
* **Style:** `UPPER_SNAKE_CASE` for constants; `snake_case` for variables/functions.

### 3. Systems & Scripts
* **Shell:** Use `#!/usr/bin/env bash` with `set -euo pipefail`.
* **Units:** Maintain `.service` and `.timer` pairs; document variables in central config files.

---

## 🧪 Testing & Validation
* **Pre-Flight:** Run the full test suite (`pytest`) before any PR submission.
* **Numbered Tests:** Enforce test order via numbered file naming (e.g., `01_test_core.py`).
* **LTS Compatibility:** Ensure all dependencies are compatible with the organization's standard OS (e.g., Ubuntu 24.04 LTS).

---

## 📄 Documentation & PR Hygiene
* **Synchronization:** Keep `README.md`, `.env`, and `config.yaml` in sync with code changes.
* **PR Template:** Every PR must include:
    - **What/Why:** High-level purpose.
    - **Risk Statement:** Impact on runtime or production stability.
    - **Testing Criteria:** Step-by-step instructions for human validation.
* **Small Batches:** Prefer small, focused PRs. Large architectural shifts require a pre-implementation design issue.

---

## ⚠️ Critical Safety Warning
**STABILITY FIRST:** If the code controls physical infrastructure or mission-critical data services, prioritize system uptime over feature velocity. Software-induced service loss is a critical failure.