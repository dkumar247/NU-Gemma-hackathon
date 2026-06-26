# Changelog

### Changed
- Update `ruff-pre-commit` to v0.15.13
- Update `uv-pre-commit` to v0.11.15
- Refine type hints for `CertParamType` in Flask CLI
- Remove unnecessary type ignore on `get_parameter_source`

### Fixed
- Handle cases where the raw JSON string is empty by returning None.
- Use .get() to safely access the "result" field in the parsed JSON data.

### Added
- Add setup instructions in README.md
