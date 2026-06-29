# Streamlit Literature Finder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local Streamlit app for searching OpenAlex literature and displaying legal access links, while keeping the existing CLI workflow intact.

**Architecture:** Create a separate `app.py` with small helper functions for OpenAlex parsing, Unpaywall lookup, filtering, sorting, and export formatting. Keep `main.py` unchanged so existing command-line usage continues to work.

**Tech Stack:** Python, Streamlit, requests, unittest, OpenAlex API, Unpaywall API.

---

### Task 1: App Helper Tests

**Files:**
- Create: `tests/test_app_helpers.py`
- Create: `app.py`

- [ ] Write failing tests for abstract reconstruction, OpenAlex result parsing, year/abstract filtering, sorting, and Markdown export.
- [ ] Run `python -m unittest tests/test_app_helpers.py -v` and confirm the tests fail because `app.py` does not exist yet.
- [ ] Implement minimal helper functions in `app.py` without rendering Streamlit UI at import time.
- [ ] Run `python -m unittest tests/test_app_helpers.py -v` and confirm the tests pass.

### Task 2: Streamlit UI

**Files:**
- Modify: `app.py`

- [ ] Add the `Literature Finder` title, keyword textarea, max-results input, optional filters, sort selector, and Search button.
- [ ] Add status messages while each keyword is searched and while Unpaywall links are checked.
- [ ] Render results with clickable URL columns where Streamlit supports them.
- [ ] Add CSV and Markdown download buttons.
- [ ] Keep Semantic Scholar disabled by default with only a future-source note in code/UI.

### Task 3: Dependencies and README

**Files:**
- Modify: `requirements.txt`
- Modify: `README.md`

- [ ] Add `streamlit` to requirements.
- [ ] Document exact Mac commands: `source .venv/bin/activate`, `pip install -r requirements.txt`, and `streamlit run app.py`.
- [ ] Confirm README still documents the CLI workflow.

### Task 4: Verification

**Files:**
- Read/verify all changed files.

- [ ] Run `python -m unittest discover -v`.
- [ ] Run `python -m py_compile main.py app.py`.
- [ ] If dependencies are installed, optionally run `streamlit run app.py` long enough to confirm startup, then stop it.
