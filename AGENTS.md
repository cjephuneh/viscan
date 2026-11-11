# VIScan agent rules

Do not edit these rule files unless the user explicitly asks to change the rules:

- `.cursor/rules/*.mdc`
- `AGENTS.md`
- `ai-interpreter/AGENTS.md`
- `ai-interpreter/CLAUDE.md`
- `ai-interpreter/tests/test_ports.py`
- the jobs and the check name `all tests passed` in `.github/workflows/ci.yml`

Read `ai-interpreter/AGENTS.md` before changing the interpreter. The screening flow calls `build_interpreter`. A new GPU host is `REMOTE_MODEL_URL`, or a new adapter in `app/services/interpreter.py`.

Keep every CI gate. Secret scan, type check, unit and integration, code injection, memory, and the AI contract run before `push training job to kaggle`. That job stays on `main` and waits for `KAGGLE_API_TOKEN`, `KAGGLE_KERNEL_SLUG`, and `KAGGLE_DATASET`. Do not commit tokens, weights, or Malhari images.

`ai-interpreter/tests/test_pipeline_gates.py` fails the build when these rules or gates are removed.
