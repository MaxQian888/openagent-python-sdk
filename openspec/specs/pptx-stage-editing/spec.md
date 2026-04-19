# pptx-stage-editing

## Purpose

Per-stage interactive editing contracts for the three stages of the PPT example where user review is substantive: intent, outline, and theme. Owned by `examples/pptx_generator/wizard/intent.py`, `wizard/outline.py`, and `wizard/theme.py`.

This capability defines how the wizard turns each agent's draft output into a reviewable-and-editable artifact rather than a single accept-or-regenerate choice. Intent becomes a field-by-field editor against `IntentReport`. Outline becomes an add/remove/reorder/edit-per-slide table against `SlideOutline`. Theme becomes a 3–5 candidate gallery with a full custom editor as fallback. The invariant across all three: every user edit SHALL be retained across questionary round-trips until an explicit `confirm`/`pick`/`accept`, and regeneration SHALL be an explicit, warn-on-loss choice.

## Requirements

### Requirement: Intent report is editable field-by-field before confirmation

After the `intent-analyst` agent returns an `IntentReport`, the wizard SHALL present a panel showing every field and offer a questionary menu with these choices: `confirm`, `edit field`, `regenerate`, `abort`. Selecting `edit field` SHALL prompt for which field (topic / audience / purpose / tone / slide_count_hint / language / required_sections / visuals_hint / research_queries) and then render the appropriate control (text / select / number / multi-value list). After each edit the updated `IntentReport` SHALL be re-rendered and the menu re-opened until the user picks `confirm` or `abort`. `confirm` SHALL persist the edited report to `project.intent`.

#### Scenario: User edits a single field

- **WHEN** the user selects `edit field → tone`, chooses `energetic`, then selects `confirm`
- **THEN** `project.intent.tone` SHALL equal `energetic`, no other field SHALL be mutated, and the stage SHALL complete

#### Scenario: User regenerates after editing

- **WHEN** the user edits the `topic` field, then selects `regenerate`
- **THEN** the agent SHALL be re-invoked with the edited `topic` fed back as the new `topic_hint`, and the returned report SHALL replace the in-memory draft (discarding prior edits)

#### Scenario: List fields accept add / remove / reorder operations

- **WHEN** the user selects `edit field → research_queries`
- **THEN** the wizard SHALL present actions `add`, `remove`, `reorder`, `edit-item`, `done`, and each action SHALL update the list accordingly

### Requirement: Outline supports add / remove / reorder / edit-per-slide

After the `outliner` agent returns a `SlideOutline`, the wizard SHALL render the outline as a Rich `Table` (index / type / title / key points) and offer a menu with: `accept`, `add slide`, `remove slide`, `reorder slides`, `edit slide`, `regenerate all`, `abort`. Editing a single slide SHALL allow changing type / title / key_points / sources_cited. After each edit the outline is re-indexed so `SlideSpec.index` is contiguous starting at 1, and the table is re-rendered.

#### Scenario: Add a slide at a chosen position

- **WHEN** the user selects `add slide`, picks position `3`, type `content`, enters title and key points
- **THEN** the new slide SHALL appear at index 3, later slides SHALL have their indices shifted by +1, and the table SHALL re-render with the updated indices

#### Scenario: Remove a slide compacts indices

- **WHEN** the user selects `remove slide → 4`
- **THEN** the slide at index 4 SHALL be deleted and subsequent slides renumbered so indices remain contiguous

#### Scenario: Reorder slides preserves per-slide content

- **WHEN** the user selects `reorder slides` and provides new ordering `[1,3,2,4,5]`
- **THEN** the slides SHALL be reordered accordingly, their `index` field SHALL match their new positions, and every other field SHALL be unchanged

#### Scenario: Regenerate-all discards edits

- **WHEN** the user has already edited a slide and then selects `regenerate all`
- **THEN** the wizard SHALL warn that local edits will be lost and SHALL only proceed if the user confirms

### Requirement: Theme stage renders a gallery of 3-5 candidates plus custom editor

The `theme-selector` agent SHALL return `candidates: list[ThemeSelection]` with 3 to 5 entries. The wizard SHALL render them side-by-side using Rich `Columns` — each candidate as a `Panel` showing the 5 palette swatches, font pairing, style, and badge style — and offer a menu with: `pick <n>`, `regenerate`, `custom editor`, `abort`. `custom editor` SHALL walk the user through every field (primary / secondary / accent / light / bg hex values; heading / body / CJK fonts; style; badge) with validators (hex 6-char no `#`) and live preview after each edit.

#### Scenario: User picks from the gallery

- **WHEN** the gallery renders 4 candidates and the user selects `pick 2`
- **THEN** `project.theme` SHALL equal the 2nd candidate verbatim, and the stage SHALL complete

#### Scenario: Custom editor validates hex input

- **WHEN** the user selects `custom editor → primary` and types `#ff0000`
- **THEN** the wizard SHALL reject the leading `#`, re-prompt with the hint "6 hex chars without #", and only accept `ff0000`

#### Scenario: Custom editor starts from the currently-selected candidate

- **WHEN** the user first picks candidate 1, then re-opens the stage via `regenerate → custom editor`
- **THEN** the custom editor SHALL pre-populate each field with candidate 1's values so the user only has to edit what they want to change
