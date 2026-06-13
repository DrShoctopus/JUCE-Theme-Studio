# Fully Managed Project Apply Mode Design

## Goal

JUCE Theme Studio should support a fully managed workflow:

1. Scan a JUCE project folder.
2. Let the user edit theme assets, layout, mappings, and colors in the app.
3. Apply the generated theme into the actual JUCE project safely.
4. Give the user a reliable way to inspect, verify, and revert the applied changes.

The core promise is: the app may update project files, but every managed write is previewed, recorded, backed up, and reversible.

## Current State

The app is currently non-destructive. It scans project source and assets, keeps editor state in `.juce_theme_studio/theme_project.json`, imports asset copies into `.juce_theme_studio/assets/`, and exports generated JSON/C++ files to `.juce_theme_studio/exports/`.

This is safe, but it stops short of the desired workflow. The user still needs to manually integrate generated files into the JUCE project.

## Proposed Workflow

The new primary flow is:

`Scan Project -> Edit Theme -> Apply Preview -> Apply Transaction -> Verify -> Revert Available`

The existing export flow remains available as a lower-risk/manual option.

Fully managed mode should be delivered in milestones. The first milestone must
make project writes and reverts trustworthy. Later milestones can add broader
source and build-file patching on top of the same transaction model.

### Apply Preview

Before touching project files, the app shows an apply preview with:

- generated files that will be copied into the project,
- source or build files that will be patched,
- files that will be created,
- files that will be overwritten,
- conflicts where the destination exists with unmanaged or unexpected content,
- validation warnings and errors,
- whether a revert snapshot can be created.

The user must explicitly confirm the apply.

### Apply Transaction

Each apply creates a transaction directory:

```text
.juce_theme_studio/applies/<apply-id>/
  apply.json
  backups/
  generated/
  patches/
```

`apply.json` records:

- apply id and timestamp,
- app version and manifest schema version,
- project root,
- export settings used,
- all created files,
- all modified files,
- pre-apply and post-apply checksums,
- backup paths,
- patch summaries,
- validation status,
- whether the apply completed or failed.

Before modifying an existing project file, the app copies its original contents into the transaction backup folder and records its checksum. If the file changes between preview and apply, the app aborts unless the user re-previews. If a managed destination already exists and does not match a prior managed apply or the current generated output, the planner marks it as a conflict instead of silently replacing it.

### Managed Output Layout

The default managed destination should be a project-local folder such as:

```text
Source/ThemeStudio/
  ThemeLayout.json
  ThemeAssets.h
  ThemeAssets.cpp
  ThemeLookAndFeel.h
  ThemeLookAndFeel.cpp
  GeneratedThemeComponents.h
  GeneratedThemeComponents.cpp
  assets/
```

The destination should be configurable, but must remain inside the project root. Absolute paths and `..` traversal are rejected.

### Source Integration

The first managed integration should support guarded edits only. The app can insert or replace code inside explicit markers:

```cpp
// JUCE_THEME_STUDIO_BEGIN
// managed content
// JUCE_THEME_STUDIO_END
```

If markers are present, the app may replace only the marked block. If markers are absent, the app may offer a patch preview and insert a new marked block only after explicit confirmation.

Initial managed patches should target:

- CMake integration for generated source files and copied assets,
- include lines for generated headers,
- calls to load `ThemeLayout.json`,
- calls to `applyScreenLayout()` for scanned JUCE components.

The implementation must avoid broad source rewrites. It should prefer small, marker-based patches with clear previews.

### Revert

The app exposes a Revert Last Apply action and an Apply History view.

Revert uses the latest completed apply transaction by default. It:

- restores modified files from transaction backups,
- removes files that were created by that apply if they are unchanged since apply,
- refuses to overwrite files that changed after apply unless the user explicitly chooses a force revert,
- records the revert result in the transaction history.

If the project is a git repository, the app should show git status before apply and revert. It should warn about unrelated dirty files and offer to create a backup branch, but it should not require git and should not auto-commit.

## Components

### Project Scanner

The existing scanner remains responsible for discovering JUCE components, C++ controls, parameter IDs, and project assets. Fully managed mode should add scanner metadata needed for integration, such as likely CMake files and candidate component implementation files.

### Exporter

The exporter should remain the generator for JSON, C++, and copied assets. Managed apply should call the exporter into a transaction staging directory first, then copy staged outputs to their managed destination.

### Apply Planner

The apply planner computes what will happen without writing to project files. It produces an `ApplyPlan` containing operations such as create file, replace file, patch marker block, copy asset, skip, and conflict.

### Apply Engine

The apply engine executes an approved `ApplyPlan` transactionally:

- verify preconditions,
- create transaction folders,
- back up existing files,
- write or patch files,
- verify checksums,
- record the result.

If a write fails mid-apply, the app should mark the transaction failed and offer rollback from backups.

### Revert Engine

The revert engine reads `apply.json`, verifies current file state, restores backups, removes unchanged created files, and records the revert result.

### UI

The UI should add:

- Apply to Project,
- Apply Preview,
- Apply History,
- Revert Last Apply.

The preview should be specific and calm: file lists, concise diffs, conflict indicators, and validation status. The user should not need to read logs to understand what will be changed.

## Safety Rules

- Never write outside the selected project root.
- Never modify project files without an apply preview and explicit confirmation.
- Never patch outside managed markers unless the user explicitly accepts that patch preview.
- Never delete an existing user file unless it was created by a recorded apply and is unchanged since that apply.
- Never auto-commit.
- Abort if previewed files changed before apply.
- Keep all transaction metadata under `.juce_theme_studio/applies/`.
- Make revert possible without git.

## Testing

Tests should cover:

- apply plan generation for a mock JUCE project,
- destination path traversal rejection,
- transaction backup creation,
- overwrite protection when files change between preview and apply,
- marker-block replacement,
- marker insertion with explicit approval,
- CMake patch preview output,
- revert of modified files,
- revert removal of unchanged created files,
- refusal to revert files changed after apply,
- operation without git,
- dirty git worktree warning behavior.

## Initial Scope

The first implementation should ship a usable managed apply/revert foundation:

- staged managed apply of exported files into `Source/ThemeStudio/`,
- transaction manifest and backups,
- apply preview,
- revert last apply,
- path safety and checksum protection,
- git dirty-state warnings.

The second implementation milestone should add marker-based CMake and source patching. That completes the fully managed integration path while keeping the first milestone focused on a reversible file transaction system.

## Out of Scope

- automatic commits,
- editing arbitrary source without markers or approved patch previews,
- supporting destinations outside the project root,
- complex semantic C++ refactoring,
- automatic build-system repair for every possible JUCE project shape.
