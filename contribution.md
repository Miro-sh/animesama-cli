# Contributing to animesama-cli

Thanks for your interest in helping! This document explains how to report bugs, propose features, and submit code.

## Reporting bugs

- Use the issue templates.
- Check that the bug hasn't already been reported.
- Include your OS, installation method (apt, dnf, AUR, pipx...), the output of `animesama-cli --debug <query>` if relevant, and screenshots when applicable.

## Requesting features

- Check the feature hasn't been requested or rejected previously.
- Describe the use case, not just the solution you have in mind.

## Getting started with code

The whole application lives in a single file, `anime_sama.py`, and runs on Python 3.9+.

```sh
git clone https://github.com/Miro-sh/animesama-cli.git
cd animesama-cli
python -m pip install -r requirements.txt
python anime_sama.py
```

The TUI requires `textual` (in `requirements.txt`); without it the app falls back to the plain CLI, which is handy for testing.

## Ground rules

- **No new dependencies unless absolutely necessary.** Prefer the standard library.
- **Keep both interfaces working.** Any playback/history change must work in the TUI *and* the CLI fallback.
- **Linux and Windows.** Avoid platform-specific APIs without a fallback for the other OS.
- UI strings are in French, code/comments/commits/docs in English.
- Appease the linter and make sure `python -m py_compile anime_sama.py` passes.
- Adjust the README according to your changes (if applicable).
- Bump the version in `pyproject.toml`.
- If you're fixing an issue, open one or link the existing one in your PR.

## Branches and commits

Create a branch from `master` with a prefixed name:

```
feat/resume-playback
fix/mpv-ipc-windows
docs/install-fedora
```

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short imperative summary>
```

| Type       | When to use it                                  |
|------------|-------------------------------------------------|
| `feat`     | New user-facing feature                         |
| `fix`      | Bug fix                                         |
| `docs`     | Documentation only (README, guides)             |
| `refactor` | Code change that neither fixes nor adds         |
| `perf`     | Performance improvement                         |
| `chore`    | Tooling, packaging, version bumps               |
| `test`     | Adding or fixing tests                          |

The scope is optional but recommended (`feat(tui): ...`, `fix(mpv): ...`). Examples from this repo:

```
feat(history): resume unfinished episodes from saved position
fix(scraper): handle missing saison2 path
chore(aur): bump to 1.0.22
```

Keep commits focused: one logical change per commit.

## Pull requests

1. Fork the repo, create your branch from `master`.
2. Follow the ground rules above.
3. Fill in the PR description: what it does, why, and how you tested it (which OS, TUI and/or CLI).
4. Link the related issue if there is one.
5. Expect a review; small PRs get merged much faster than big ones.

Releases are made by the maintainer only: pushing a `v*` tag triggers the workflow that publishes to PyPI, AUR, the apt/dnf repositories, and the Homebrew tap. Don't push tags yourself.

## How else can I help?

- Join the [Discord](https://discord.gg/MwHAXPpJ8C)
- Star the repo
- Follow the maintainers
