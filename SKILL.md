---
name: remote-tmux-coding-skill
description: Manage tmux-backed coding agents, including session lifecycle, SSH remote access, and FTP file transfer workflows. Use when creating, attaching to, watching, sending input to, restarting, adopting, or auditing tmux-based agents, or when coordinating remote access over SSH or legacy FTP.
---

# Remote Tmux Coding Skill

## Overview

Use this skill to control long-running coding agents through tmux sessions.
It covers session creation, attach/watch/send/capture flows, policy gating,
audit logging, SSH-based remote access, and FTP-based artifact transfer when
legacy systems require it.

## Core Workflow

1. Create or adopt an agent session with `./rtmux.py create ...` or
   `./rtmux.py adopt ...`.
2. Inspect or drive the session with `list`, `status`, `watch`, `capture`,
   `send`, `enter`, `restart`, `kill`, and `audit`.
3. Use `policy` to constrain which operations are allowed for each agent.

## SSH

- Prefer SSH for all remote host access.
- Use SSH tunnels for control surfaces instead of exposing tmux over TCP.
- Use `ssh`, `scp`, or `sftp` to reach the remote host and transfer files.
- When a remote host already runs tmux, manage the session on that host and
  keep the control path local to SSH.

See [SSH reference](references/ssh.md).

## FTP

- Use FTP only when a legacy server requires it.
- Prefer SFTP or FTPS if available.
- Use FTP for simple artifact upload/download flows tied to agent inputs,
  logs, or generated outputs.
- Avoid sending secrets over plaintext FTP.

See [FTP reference](references/ftp.md).

## Operational Rules

- Keep one tmux session per agent.
- Use `watch` for read-only observation.
- Use `send --no-enter` when staging a command before execution.
- Record important changes with `audit`.
- Keep control local to the machine running tmux; do not expose a public
  control port.

## Resources

- `rtmux.py`: CLI implementation.
- `references/ssh.md`: SSH patterns and safe remote access guidance.
- `references/ftp.md`: FTP transfer patterns and cautions.
