# rtmux

`rtmux` is a small tmux-backed CLI for controlling long-running local or remote
agent sessions. It keeps each agent in a dedicated tmux session, stores local
metadata in JSON, and provides simple policy gates for sending input, attaching,
and killing sessions.

## Requirements

- Python 3.8+
- tmux

No Python package dependencies are required.

## Quick Start

Initialize local state:

```bash
./rtmux.py init
```

Create an agent session:

```bash
./rtmux.py create agent1 --cmd "codex" --cwd /home/david/project
```

List managed agents:

```bash
./rtmux.py list
```

Attach to the tmux session:

```bash
./rtmux.py attach agent1
```

Send input to the agent:

```bash
./rtmux.py send agent1 "continue the task"
```

Capture recent output:

```bash
./rtmux.py capture agent1 --lines 100
```

Stop and remove the agent record:

```bash
./rtmux.py kill agent1 --forget
```

## Commands

```text
init                         create .rtmux/agents.json
create NAME --cmd CMD        create and start a managed tmux session
list                         list known agents and running state
status NAME                  print one agent as JSON
attach NAME                  attach to the agent's tmux session
send NAME TEXT               send text plus Enter
send NAME TEXT --no-enter    send text without pressing Enter
enter NAME                   send only Enter
capture NAME                 print recent tmux pane output
watch NAME                   read-only live output view
restart NAME                 restart an agent from saved state
adopt NAME --cmd CMD         record an existing tmux session as an agent
policy NAME                  show or update permissions
audit                        print recent audit log records
kill NAME                    kill the tmux session
forget NAME                  remove state without killing tmux
```

## Examples

Use a clean shell for testing:

```bash
./rtmux.py create test --cmd /bin/sh --cwd "$PWD"
./rtmux.py send test 'echo hello'
./rtmux.py capture test
./rtmux.py kill test --forget
```

Type first, then confirm with Enter:

```bash
./rtmux.py send agent1 "npm test" --no-enter
./rtmux.py enter agent1
```

Temporarily block remote input:

```bash
./rtmux.py policy agent1 --send deny
./rtmux.py policy agent1 --send allow
```

Adopt an existing tmux session:

```bash
tmux new-session -d -s rtmux-existing -c "$PWD" /bin/sh
./rtmux.py adopt existing --cmd /bin/sh --cwd "$PWD"
```

## State and Audit Logs

By default, state is stored under the current working directory:

```text
.rtmux/
  agents.json
  audit.log
```

Use `RTMUX_HOME` to place state somewhere else:

```bash
RTMUX_HOME=~/.rtmux ./rtmux.py list
```

Audit records are JSON Lines:

```bash
./rtmux.py audit --lines 50
```

## Policy Model

Each agent has three local permission flags:

- `send`: allow or deny `send` and `enter`
- `attach`: allow or deny interactive tmux attach
- `kill`: allow or deny killing or restarting an active session

Set policy while creating an agent:

```bash
./rtmux.py create observer --cmd /bin/sh --no-send --no-kill
```

Update policy later:

```bash
./rtmux.py policy observer --send allow --kill deny
```

## Notes

- tmux session names use the `rtmux-` prefix.
- `watch` is read-only and does not attach to the tmux session.
- If your login shell prompts on startup, prefer a direct command such as
  `/bin/sh`, `codex`, or another agent command instead of an interactive shell.
