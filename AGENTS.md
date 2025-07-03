# AGENT Instructions

## Development
- Run `tox -e py,linting,mypy` before committing code changes. This runs the unit tests, lints and mypy checks with the default Python version.
- When documentation is changed, also run `tox -e docbuild,doclinting` to ensure docs build successfully.
- Use `pre-commit` for formatting with Black and other linters: `tox -e pre-commit -- run --files <files>`.
- Follow `.editorconfig` settings (spaces, newline at EOF) and keep code formatted with `black`.
- Don't update `CHANGELOG.md`.

## Pull Request Message
- Include a bullet list summary of changes and mention any related issues (e.g. `fixes #123`).
- Summarize test execution in a separate **Testing** section, mentioning `tox` commands run and their result.
- If tests cannot run due to environment limits, state this in the **Testing** section.
