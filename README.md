# remote_tmux_coding_skill

This repository contains a Codex skill and a small tmux-backed CLI for managing
long-running coding agents.

## What It Does

- Create one tmux session per agent
- Attach to or watch running agents
- Send input in a controlled way
- Restart or adopt existing tmux sessions
- Record audit events locally
- Support SSH-based remote access workflows
- Document legacy FTP transfer workflows when needed

## Requirements

- Python 3.8+
- `tmux`

No Python packages are required.

## Usage

Run the CLI directly from the repository:

```bash
./rtmux.py init
./rtmux.py create agent1 --cmd /bin/sh --cwd "$PWD"
./rtmux.py list
./rtmux.py attach agent1
./rtmux.py send agent1 "echo hello"
./rtmux.py send agent1 "npm test" --no-enter
./rtmux.py enter agent1
./rtmux.py capture agent1 --lines 100
./rtmux.py watch agent1
./rtmux.py restart agent1
./rtmux.py audit --lines 50
```

## State Files

By default, state is stored in `.rtmux/` under the current working directory.
Set `RTMUX_HOME` to move it elsewhere:

```bash
RTMUX_HOME=~/.rtmux ./rtmux.py list
```

## Skill Layout

- `SKILL.md`: skill entry point and usage rules
- `references/ssh.md`: SSH workflows and safe remote access patterns
- `references/ftp.md`: FTP workflows for legacy transfers
- `agents/openai.yaml`: UI metadata for Codex skill lists

## Installing As A Codex Skill

Clone or copy this repository into your Codex skills directory so it is
discoverable as `remote-tmux-coding-skill`.

Example:

```bash
git clone https://github.com/binicey/remote_tmux_coding_skill.git \
  ~/.codex/skills/remote-tmux-coding-skill
```

Then invoke it explicitly with `$remote-tmux-coding-skill` or let Codex load it
when a tmux, SSH, or FTP workflow is requested.

## Notes

- `watch` is read-only.
- `send --no-enter` stages input without running it.
- Prefer SSH or SFTP over FTP when possible.
- Keep tmux control local to the machine that runs the sessions.
