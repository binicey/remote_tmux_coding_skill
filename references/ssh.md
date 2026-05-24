# SSH Reference

## When To Use

Use SSH for remote host access, session control, and file movement whenever the
target machine supports it.

## Common Patterns

### Open A Tunneling Channel

```bash
ssh -L /tmp/rtmux.sock:/home/user/.rtmux/control.sock user@host
```

Use a tunnel when the control channel must stay local to the remote host.

### Run Commands Remotely

```bash
ssh user@host 'cd /path/to/project && ./rtmux.py list'
```

### Copy Files

```bash
scp output.log user@host:/tmp/
```

```bash
sftp user@host
```

## Guidance

- Prefer SSH keys over passwords.
- Prefer local tmux control on the remote machine instead of exposing a raw
  control port.
- Use `scp` or `sftp` for file transfer rather than ad hoc shell piping.
- If a remote session is already active, use `./rtmux.py adopt ...` only after
  confirming the session name and command.
