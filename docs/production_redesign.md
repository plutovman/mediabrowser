# Production nav bar redesign: legacy cascade → consolidated JOB OPS / JOB: bar

This document describes a UI redesign carried out on `production.html`/`projectbrowser.py` in the
mediabrowser project, written up generally enough to reuse the same approach on a similar
Flask + vanilla-JS cascading-dropdown interface. See `production_layout.png` in this same directory
for the reference mockup that drove the new layout.

## Problem

The original nav bar (`JOB SET ▾ | JOB SYNC ▾ | JOB NEW | RESEARCH | ARCHIVE`) conflated two
different concerns into one cascade: **picking which job to work on**, and **acting on that job**
(navigating into its directories, or synchronizing them). Both `JOB SET` and `JOB SYNC` independently
forced the user through the full storage → year → project → app cascade every time, even though
"which job" rarely changes between actions performed on it.

## Design principle (the reusable part)

Separate **"set a target"** from **"act on the target"**, and let the second concern become a
short, flat menu keyed off whatever's currently set, instead of re-deriving the target every time:

- One menu picks/creates the target and stores it in state (both client-side, for immediate menu
  behavior, and persisted server-side, so it survives a reload).
- A second menu, disabled until a target is set, shows the target's identity and offers actions on
  it directly — no re-navigation through the picker hierarchy.
- Any storage/direction choice that only matters for the *action* (not for identifying the target)
  moves from the front of the cascade to the point where it's actually consumed.

This generalizes past this specific job/nav-directory case: any UI with a "pick X, then do several
different things to X" shape benefits from this split once the picker cascade gets deep enough that
re-walking it for every action becomes the dominant friction.

## Before / after

```
BEFORE:  JOB SET ▾ (storage → year → project → app)   JOB SYNC ▾ (direction → year → project → app)   JOB NEW
AFTER:   JOB OPS ▾ (NEW JOB | SET JOB → year → project)   JOB: <name> ▾ (JOB NAV → storage → app | JOB SYNC → direction → app)
```

`JOB:` is greyed out / non-interactive (`opacity: 0.5; pointer-events: none`) until a job is set via
`JOB OPS → SET JOB`. Once set, its label shows the job name and its two sub-actions (`JOB NAV`,
`JOB SYNC`) operate directly on that job — no year/project re-selection.

## Implementation approach

### 1. Reuse business logic; only build new menu chrome

Before writing anything new, trace the existing click/hover handlers for the "act on X" cascade and
confirm they're already parameterized generically (i.e. they take "which thing" as a plain
argument/object, not derived from DOM state specific to one menu). In this project:

- The function that actually does the app-directory-open / sync-confirm action already accepted
  `(project, isSync, syncDirection, storage)` where `project = {name, path}` — it didn't care *how*
  that was obtained. So the new "act on the already-set job" menu could call it directly with the
  persisted job, skipping the picker cascade entirely, with **zero changes** to that function.
- The "set a target" click handler (clicking a leaf in the picker) already existed too (it's what
  the old bar did when you clicked a project name without drilling into an app) — the new picker
  menu is that same interaction, just reached by a shorter path.

If your equivalent functions are hardcoded to the *old* menu's DOM elements/IDs instead of taking
their subject as a parameter, refactor them to take a parameter **first**, as a standalone step — it
pays for itself immediately once you stop duplicating logic in the new menu.

### 2. Extend shared functions with a trailing optional parameter; don't fork them

Two places needed a small behavior change from the new menu that the old menu doesn't want:

- **A completion callback.** The picker's leaf-click handler does its normal thing (show a details
  panel) *and*, only for the new menu, also needs to update the "target is now set" state. Added one
  new trailing parameter with a default that preserves old behavior exactly
  (`onSelected = null`, only invoked `if (onSelected) { onSelected(...) }`), rather than writing a
  second copy of the click handler. All existing call sites are untouched because they simply don't
  pass the new argument.
- **A "how deep does this cascade go" toggle.** The picker cascade used by the *old* bar also lazily
  builds one more level (apps) on hover past the leaf the new menu wants to stop at. Added a second
  trailing boolean parameter (`showNextLevel = true`) that gates whether that next-level hover
  listener gets attached at all. Same pattern: default preserves old behavior, new call site passes
  `false`.

General rule: when a shared function needs new behavior for exactly one new caller, add an optional
parameter with a default equal to the current behavior, rather than branching internally on caller
identity or duplicating the function. Every existing call site should be untouched in the diff.

### 3. New markup + parallel, namespaced CSS — don't touch the old bar's markup/CSS

If the old UI needs to keep working unmodified while the new one is built (e.g. for direct
comparison during development, or because it's not ready to fully replace the old one yet):

- Give every new element a distinct `id`, and put the new markup in its own container placed after
  the old one (e.g. a second centered flex container below the first).
- If the existing CSS for the cascading-dropdown behavior is **ID-scoped** (`#old-menu-id ul`,
  `#old-menu-id li:hover > ul`, etc. — common for this kind of hand-rolled multilevel menu, since
  class-based scoping would apply to menus you don't want it to), you cannot reuse those rules for a
  new container just by giving it the same classes. The pragmatic fix is a **parallel CSS block**
  scoped to the new container's id, mirroring the existing rules 1:1. It's some duplication, but it
  guarantees the old bar's stylesheet is untouched, and it's trivial to delete once the old bar is
  retired (delete the old rules, rename the new container's id to the canonical one).

### 4. Watch for helper functions that assume "there is only one nav bar"

Generic helpers like "close all open dropdown menus" or "hide all result panels" are easy to write
against `document.querySelector(...)` (singular) when there's only one instance of the thing on the
page. Adding a second nav bar surfaces this immediately — `querySelector` silently returns only the
*first* match, so a global "close menus" call from the new bar would incorrectly only affect (or fail
to affect) the old one. Fix: broaden to `querySelectorAll(...).forEach(...)`. This is safe and
backward-compatible as long as the function's job is genuinely "do this for every instance," which
it usually is for these kinds of page-level utility functions.

### 5. Persisting a "currently set" target across reloads

If the picked target needs to survive a page reload and a server-side session isn't the right
mechanism (e.g. you want it to persist even after a server restart, or want it visible outside the
session/cookie system), a plain JSON file at a fixed, predictable location works well and is the
simplest possible implementation:

```python
path_settings_dir = os.path.join(os.path.expanduser('~'), 'Documents', '<app-name>')
path_settings_file = os.path.join(path_settings_dir, 'settings.json')

def _active_target_read():
    if not os.path.exists(path_settings_file):
        return None
    try:
        with open(path_settings_file, 'r') as f:
            data = json.load(f)
        ...
    except (OSError, json.JSONDecodeError):
        return None  # never let a corrupt/missing settings file break the page

def _active_target_write(...):
    os.makedirs(path_settings_dir, exist_ok=True)
    with open(path_settings_file, 'w') as f:
        json.dump(..., f, indent=2)
```

- Read it once, server-side, on the page route, and inject it into the template as a JSON literal
  (`let activeTarget = {{ active_target|tojson }};`) — cheaper than a client-side fetch on load, and
  matches however the rest of the page already injects server-computed values into the script.
  Restoring should only update passive UI state (a label, an enabled/disabled class) — don't
  auto-trigger the same side effects a live user action would (e.g. don't auto-open a details panel
  just because a target was restored from disk).
- Write it via a small dedicated POST endpoint, called from the "target selected" callback described
  in step 2.
- Always fail soft on read (missing file, missing directory, corrupt JSON → treat as "nothing set"),
  since this file is disposable UI convenience state, not a source of truth.

## Gotchas hit during this implementation (worth checking for in a similar redesign)

- **Don't assume environment/config parity between test runs.** After finishing the initial
  implementation, a real behavioral regression was reported (a storage-local/network path
  substitution stopped working). Directly testing the affected backend function in isolation proved
  the logic itself was untouched and correct — the actual cause was that the *particular server
  process* used for that round of testing was missing two environment variables the substitution
  depends on (they'd never been exported in that shell), unrelated to any code change. Lesson: when a
  "it broke" report comes in for logic you're confident wasn't touched, verify the exact runtime
  config of the specific process being tested before assuming a code regression — isolate the
  function directly (call it from a one-off script/REPL with explicit inputs) to separate "code is
  wrong" from "environment is wrong."
- **A cascade-depth mismatch is easy to miss.** The new "set target" picker initially reused the old
  picker's hover behavior wholesale, which included lazily building one extra menu level (apps) that
  the new design didn't want at that point (that level belongs to the *separate* "act on target"
  menu now). This is exactly the kind of thing that "looks right" in a quick pass because the picker
  still functions, and only becomes obvious when someone walks the actual click path level by level.
- **Iterate on presentation details as a separate pass.** Wording, button widths, default/placeholder
  text, and a temporary "WIP" visual marker were all adjusted after the structural implementation was
  confirmed working — deliberately kept separate from the functional changes so each round of tweaks
  had a small, easy-to-verify diff.

## Verification checklist used

1. Old bar still behaves identically end-to-end (every leaf action, both storage/direction choices).
2. New bar: create-target action produces the same result as the old bar's equivalent.
3. New bar: set-target action stops the cascade at the right depth (no premature extra level).
4. New bar: each act-on-target action produces the *same* result the old bar's equivalent produces
   for the same target/parameters (directly diffed the resolved paths, not just "it opened
   something").
5. Reload with no persisted target → target menu shows a clear disabled/placeholder state.
6. Set a target, reload → target menu immediately reflects it without re-selection.
7. Delete the persisted-state file, reload → falls back to the disabled/placeholder state cleanly
   (no error, no stale UI).
8. A generic "close menus" style helper (see gotcha above) still closes whichever bar is actually
   open, not just the first one on the page.
