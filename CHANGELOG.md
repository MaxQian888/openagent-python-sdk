## [Unreleased]

### Added
- Added `pattern.execute` capability with `PatternPlugin.execute` and full ReAct loop support (max steps and per-step timeout).
- Added builtin tool registry entries for file, text, HTTP, and system operations.

### Changed
- Runtime now delegates pattern execution to `PatternPlugin.execute` and no longer emits pattern step lifecycle events.
- Pattern loading now requires `pattern.execute` capability and validates `execute` implementation.
