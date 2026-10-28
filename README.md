# pi-config

Personal configuration for [pi](https://github.com/earendil-works/pi), the
terminal coding agent. This repository *is* the agent directory: pi reads it
from `~/.pi/agent`.

## Layout

| Path | Responsibility |
| --- | --- |
| `settings.json` | User settings (theme, default provider/model, thinking level) |
| `APPEND_SYSTEM.md` | Instructions appended to pi's system prompt |
| `skills/` | User skills, exposed as `/skill:<name>` |
| `prompts/` | Prompt templates, exposed as slash commands |
| `themes/` | Custom themes (`system` is built in and follows the terminal) |
| `extensions/` | Extensions loaded on startup |

## Not tracked

Credentials and machine-local state stay out of git (see `.gitignore`):
`auth.json`, `trust.json`, `models-store.json`, `sessions/`, and the `npm/`,
`git/`, `tmp/`, `bin/` directories pi manages itself.

## Setup on a new machine

```bash
git clone https://github.com/hasundue/pi-config ~/.pi/agent
pi /login   # write auth.json locally
```

Set `PI_CODING_AGENT_DIR` only if the checkout lives somewhere else.

## Notes

- `settings.json` is written by pi itself (`/settings`, `pi update`), so commit
  the changes you want to keep. Keys are merged by pi, not replaced.
- Nix does not manage this directory. Package installation and self-updates go
  through pi's own tooling.
