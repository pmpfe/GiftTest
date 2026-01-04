# GitHub Copilot Instructions (GiftTest)

## Project context
- This repository is a **PySide6 (Qt6) GUI app** for practicing quizzes from **GIFT** files.
- Main entry point is `main.py` and most UI is split into “screens” under `data/`.
- The app already targets lightweight UI components (e.g., QTextBrowser for HTML rendering).

## General coding principles
- Keep solutions **simple and readable**. Prefer straightforward code over clever abstractions.
- Make changes **surgically**: modify the smallest area needed; avoid unrelated refactors.
- Prefer existing project patterns and structure:
  - UI screens belong in `data/*_screen.py`.
  - Parsing/logic lives in `data/` modules (e.g., `data/gift_parser.py`).
- Avoid adding new dependencies unless absolutely necessary.

## UI/UX constraints (important)
- Keep the UI **minimal and consistent** so it can be reused on **mobile platforms** later.
  - Prefer simple layouts, fewer widgets, and predictable navigation.
  - Avoid complex nested layouts, heavyweight custom painting, and intricate UI state.
  - Favor responsive sizing using existing preferences (percentage-of-screen sizing) instead of hard-coded sizes.
- Do not introduce new pages, modals, animations, or “nice-to-have” features unless explicitly requested.
- Avoid UI that assumes mouse/keyboard-only interactions; keep controls touch-friendly where practical.

## Documentation policy
- Keep documentation **minimal**.
- If documentation is needed, update **README.md** only.
- Do not create new markdown docs, wikis, or extensive inline comments.

## Error handling and reliability
- Handle expected failures gracefully (missing GIFT file, network errors, timeouts) without crashing.
- In the GUI, prefer showing errors via `QMessageBox` rather than printing stack traces.
- Do not block the UI thread with network calls; use the existing QThread worker pattern when needed.

## Code style and maintainability
- Use descriptive names; avoid one-letter variables except for trivial loops.
- Keep functions short and focused.
- Prefer type hints where they improve clarity, but do not over-annotate.
- Preserve existing formatting and conventions in each file.

## Testing and verification
- If you change parsing or business logic, add/adjust a small verification path (e.g., by extending existing scripts under `util/` if present) only when appropriate.
- Do not add a full new test framework unless asked.

## When uncertain
- If requirements are ambiguous, choose the **simplest** interpretation that fits the current app design.
- Ask at most 1–3 clarifying questions before implementing a potentially large UI change.
