#!/usr/bin/env python3
"""Small tmux-backed controller for local/remote agent sessions."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


APP_DIR_ENV = "RTMUX_HOME"
SESSION_PREFIX = "rtmux-"


class RtmuxError(RuntimeError):
    pass


@dataclass
class Agent:
    name: str
    session: str
    cmd: str
    cwd: str
    created_at: str
    allow_send: bool = True
    allow_attach: bool = True
    allow_kill: bool = True
    env: dict[str, str] = field(default_factory=dict)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def app_dir() -> Path:
    override = os.environ.get(APP_DIR_ENV)
    return Path(override).expanduser() if override else Path.cwd() / ".rtmux"


def state_path() -> Path:
    return app_dir() / "agents.json"


def audit_path() -> Path:
    return app_dir() / "audit.log"


def audit(action: str, agent: str | None = None, **details: Any) -> None:
    path = audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": now_iso(),
        "action": action,
        "agent": agent,
        "details": details,
    }
    with path.open("a", encoding="utf-8") as fh:
        json.dump(record, fh, sort_keys=True)
        fh.write("\n")


def load_state() -> dict[str, Any]:
    path = state_path()
    if not path.exists():
        return {"agents": {}}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise RtmuxError(f"state file is not valid JSON: {path}: {exc}") from exc

    if not isinstance(data, dict) or not isinstance(data.get("agents"), dict):
        raise RtmuxError(f"state file has unexpected structure: {path}")
    return data


def save_state(state: dict[str, Any]) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
        fh.write("\n")
    tmp.replace(path)


def load_agent(name: str) -> Agent:
    state = load_state()
    raw = state["agents"].get(name)
    if raw is None:
        raise RtmuxError(f"unknown agent: {name}")
    return Agent(**raw)


def run_tmux(args: list[str], *, check: bool = True, text: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = ["tmux", *args]
    try:
        return subprocess.run(
            cmd,
            check=check,
            capture_output=True,
            text=text,
        )
    except FileNotFoundError as exc:
        raise RtmuxError("tmux is not installed or not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or "").strip()
        raise RtmuxError(message or f"tmux command failed: {' '.join(cmd)}") from exc


def session_name(agent_name: str) -> str:
    return f"{SESSION_PREFIX}{agent_name}"


def valid_name(value: str) -> str:
    if not value:
        raise argparse.ArgumentTypeError("name cannot be empty")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-")
    if any(ch not in allowed for ch in value):
        raise argparse.ArgumentTypeError("use only letters, numbers, dot, underscore, and dash")
    return value


def tmux_has_session(session: str) -> bool:
    result = run_tmux(["has-session", "-t", session], check=False)
    return result.returncode == 0


def tmux_sessions() -> set[str]:
    result = run_tmux(["list-sessions", "-F", "#{session_name}"], check=False)
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def ensure_policy(agent: Agent, action: str) -> None:
    field_name = f"allow_{action}"
    if not getattr(agent, field_name, False):
        raise RtmuxError(f"policy denies {action} for agent: {agent.name}")


def start_session(agent: Agent, *, replace: bool = False) -> None:
    if tmux_has_session(agent.session):
        if not replace:
            raise RtmuxError(f"tmux session already exists: {agent.session}")
        run_tmux(["kill-session", "-t", agent.session])

    if not Path(agent.cwd).is_dir():
        raise RtmuxError(f"cwd is not a directory: {agent.cwd}")

    tmux_args = ["new-session", "-d", "-s", agent.session, "-c", agent.cwd]
    for key, value in agent.env.items():
        tmux_args.extend(["-e", f"{key}={value}"])
    tmux_args.append(agent.cmd)
    run_tmux(tmux_args)


def cmd_init(_: argparse.Namespace) -> int:
    state = load_state()
    save_state(state)
    audit("init")
    print(f"initialized {state_path()}")
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    name = args.name
    state = load_state()
    if name in state["agents"] and not args.replace:
        raise RtmuxError(f"agent already exists: {name} (use --replace to recreate)")

    cwd = str(Path(args.cwd).expanduser().resolve())
    if not Path(cwd).is_dir():
        raise RtmuxError(f"cwd is not a directory: {cwd}")

    env = {}
    for item in args.env or []:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise RtmuxError(f"invalid --env value, expected KEY=VALUE: {item}")
        env[key] = value

    full_cmd = args.cmd
    agent = Agent(
        name=name,
        session=session_name(name),
        cmd=full_cmd,
        cwd=cwd,
        created_at=now_iso(),
        allow_send=not args.no_send,
        allow_attach=not args.no_attach,
        allow_kill=not args.no_kill,
        env=env,
    )
    start_session(agent, replace=args.replace)
    state["agents"][name] = asdict(agent)
    save_state(state)
    audit("create", name, session=agent.session, cmd=agent.cmd, cwd=agent.cwd)
    print(f"created {name} -> {agent.session}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    state = load_state()
    live = tmux_sessions()
    agents = state["agents"]
    if not agents:
        print("no agents")
        return 0

    if args.json:
        output = []
        for raw in agents.values():
            agent = Agent(**raw)
            item = asdict(agent)
            item["running"] = agent.session in live
            output.append(item)
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0

    print(f"{'NAME':24} {'STATE':8} {'SESSION':28} CWD")
    for name in sorted(agents):
        agent = Agent(**agents[name])
        state_text = "running" if agent.session in live else "stopped"
        print(f"{agent.name:24} {state_text:8} {agent.session:28} {agent.cwd}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    agent = load_agent(args.name)
    data = asdict(agent)
    data["running"] = tmux_has_session(agent.session)
    print(json.dumps(data, indent=2, sort_keys=True))
    return 0


def cmd_attach(args: argparse.Namespace) -> int:
    agent = load_agent(args.name)
    ensure_policy(agent, "attach")
    if not tmux_has_session(agent.session):
        raise RtmuxError(f"agent is not running: {agent.name}")
    audit("attach", agent.name, session=agent.session)
    os.execvp("tmux", ["tmux", "attach-session", "-t", agent.session])
    return 0


def cmd_send(args: argparse.Namespace) -> int:
    agent = load_agent(args.name)
    ensure_policy(agent, "send")
    if not tmux_has_session(agent.session):
        raise RtmuxError(f"agent is not running: {agent.name}")
    tmux_args = ["send-keys", "-t", agent.session, args.text]
    if not args.no_enter:
        tmux_args.append("Enter")
    run_tmux(tmux_args)
    audit("send", agent.name, enter=not args.no_enter, text=args.text)
    suffix = "" if args.no_enter else " + Enter"
    print(f"sent to {agent.name}{suffix}: {args.text}")
    return 0


def cmd_enter(args: argparse.Namespace) -> int:
    agent = load_agent(args.name)
    ensure_policy(agent, "send")
    if not tmux_has_session(agent.session):
        raise RtmuxError(f"agent is not running: {agent.name}")
    run_tmux(["send-keys", "-t", agent.session, "Enter"])
    audit("enter", agent.name)
    print(f"sent Enter to {agent.name}")
    return 0


def cmd_capture(args: argparse.Namespace) -> int:
    agent = load_agent(args.name)
    if not tmux_has_session(agent.session):
        raise RtmuxError(f"agent is not running: {agent.name}")
    start = f"-{args.lines}"
    result = run_tmux(["capture-pane", "-t", agent.session, "-p", "-S", start])
    output = result.stdout.rstrip("\n")
    if output:
        print(output)
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    agent = load_agent(args.name)
    if not tmux_has_session(agent.session):
        raise RtmuxError(f"agent is not running: {agent.name}")
    audit("watch", agent.name, interval=args.interval, lines=args.lines)
    watch_cmd = f"tmux capture-pane -t {agent.session} -p -S -{args.lines}"
    os.execvp("watch", ["watch", "-n", str(args.interval), watch_cmd])
    return 0


def cmd_kill(args: argparse.Namespace) -> int:
    agent = load_agent(args.name)
    ensure_policy(agent, "kill")
    if tmux_has_session(agent.session):
        run_tmux(["kill-session", "-t", agent.session])

    if args.forget:
        state = load_state()
        state["agents"].pop(args.name, None)
        save_state(state)
        audit("kill", args.name, forget=True)
        print(f"killed and forgot {args.name}")
    else:
        audit("kill", args.name, forget=False)
        print(f"killed {args.name}")
    return 0


def cmd_forget(args: argparse.Namespace) -> int:
    state = load_state()
    if args.name not in state["agents"]:
        raise RtmuxError(f"unknown agent: {args.name}")
    state["agents"].pop(args.name)
    save_state(state)
    audit("forget", args.name)
    print(f"forgot {args.name}")
    return 0


def cmd_policy(args: argparse.Namespace) -> int:
    state = load_state()
    raw = state["agents"].get(args.name)
    if raw is None:
        raise RtmuxError(f"unknown agent: {args.name}")

    agent = Agent(**raw)
    changed = False
    for action in ("send", "attach", "kill"):
        value = getattr(args, action)
        if value is not None:
            setattr(agent, f"allow_{action}", value == "allow")
            changed = True

    if not changed:
        print(
            json.dumps(
                {
                    "send": agent.allow_send,
                    "attach": agent.allow_attach,
                    "kill": agent.allow_kill,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    state["agents"][args.name] = asdict(agent)
    save_state(state)
    audit(
        "policy",
        args.name,
        send=agent.allow_send,
        attach=agent.allow_attach,
        kill=agent.allow_kill,
    )
    print(f"updated policy for {args.name}")
    return 0


def cmd_restart(args: argparse.Namespace) -> int:
    agent = load_agent(args.name)
    if tmux_has_session(agent.session):
        ensure_policy(agent, "kill")
    start_session(agent, replace=True)
    audit("restart", agent.name, session=agent.session)
    print(f"restarted {agent.name} -> {agent.session}")
    return 0


def cmd_adopt(args: argparse.Namespace) -> int:
    name = args.name
    state = load_state()
    if name in state["agents"] and not args.replace:
        raise RtmuxError(f"agent already exists: {name} (use --replace to overwrite state)")

    session = args.session or session_name(name)
    if not tmux_has_session(session):
        raise RtmuxError(f"tmux session does not exist: {session}")

    cwd = str(Path(args.cwd).expanduser().resolve())
    if not Path(cwd).is_dir():
        raise RtmuxError(f"cwd is not a directory: {cwd}")

    agent = Agent(
        name=name,
        session=session,
        cmd=args.cmd,
        cwd=cwd,
        created_at=now_iso(),
        allow_send=not args.no_send,
        allow_attach=not args.no_attach,
        allow_kill=not args.no_kill,
        env={},
    )
    state["agents"][name] = asdict(agent)
    save_state(state)
    audit("adopt", name, session=session, cmd=args.cmd, cwd=cwd)
    print(f"adopted {name} -> {session}")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    path = audit_path()
    if not path.exists():
        return 0
    lines = path.read_text(encoding="utf-8").splitlines()
    selected = lines[-args.lines :] if args.lines else lines
    for line in selected:
        print(line)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rtmux",
        description="Control tmux-backed agent sessions.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create the local state directory")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("create", help="create and start an agent session")
    p.add_argument("name", type=valid_name)
    p.add_argument("--cmd", required=True, help="command to run in the tmux session")
    p.add_argument("--cwd", default=".", help="working directory for the session")
    p.add_argument("--env", action="append", help="environment variable as KEY=VALUE")
    p.add_argument("--replace", action="store_true", help="replace existing state/session")
    p.add_argument("--no-send", action="store_true", help="deny send operations")
    p.add_argument("--no-attach", action="store_true", help="deny attach operations")
    p.add_argument("--no-kill", action="store_true", help="deny kill operations")
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("list", help="list known agents")
    p.add_argument("--json", action="store_true", help="print machine-readable JSON")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("status", help="show one agent as JSON")
    p.add_argument("name", type=valid_name)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("attach", help="attach to an agent tmux session")
    p.add_argument("name", type=valid_name)
    p.set_defaults(func=cmd_attach)

    p = sub.add_parser("send", help="send one line of input to an agent")
    p.add_argument("name", type=valid_name)
    p.add_argument("text", help="text to send")
    p.add_argument("--no-enter", action="store_true", help="send text without pressing Enter")
    p.set_defaults(func=cmd_send)

    p = sub.add_parser("enter", help="send only Enter to an agent")
    p.add_argument("name", type=valid_name)
    p.set_defaults(func=cmd_enter)

    p = sub.add_parser("capture", help="print recent output from an agent")
    p.add_argument("name", type=valid_name)
    p.add_argument("--lines", type=int, default=100, help="number of recent lines")
    p.set_defaults(func=cmd_capture)

    p = sub.add_parser("watch", help="read-only live view of recent agent output")
    p.add_argument("name", type=valid_name)
    p.add_argument("--lines", type=int, default=80, help="number of recent lines")
    p.add_argument("--interval", type=float, default=1.0, help="refresh interval in seconds")
    p.set_defaults(func=cmd_watch)

    p = sub.add_parser("kill", help="kill an agent session")
    p.add_argument("name", type=valid_name)
    p.add_argument("--forget", action="store_true", help="also remove it from state")
    p.set_defaults(func=cmd_kill)

    p = sub.add_parser("restart", help="restart an agent from saved state")
    p.add_argument("name", type=valid_name)
    p.set_defaults(func=cmd_restart)

    p = sub.add_parser("adopt", help="record an existing tmux session as an agent")
    p.add_argument("name", type=valid_name)
    p.add_argument("--session", help="existing tmux session name, defaults to rtmux-NAME")
    p.add_argument("--cmd", required=True, help="command to save for future restart")
    p.add_argument("--cwd", default=".", help="working directory to save for future restart")
    p.add_argument("--replace", action="store_true", help="replace existing agent state")
    p.add_argument("--no-send", action="store_true", help="deny send operations")
    p.add_argument("--no-attach", action="store_true", help="deny attach operations")
    p.add_argument("--no-kill", action="store_true", help="deny kill operations")
    p.set_defaults(func=cmd_adopt)

    p = sub.add_parser("forget", help="remove an agent from state without killing tmux")
    p.add_argument("name", type=valid_name)
    p.set_defaults(func=cmd_forget)

    p = sub.add_parser("policy", help="show or update an agent policy")
    p.add_argument("name", type=valid_name)
    for action in ("send", "attach", "kill"):
        p.add_argument(f"--{action}", choices=("allow", "deny"), help=f"set {action} permission")
    p.set_defaults(func=cmd_policy)

    p = sub.add_parser("audit", help="print recent audit log records")
    p.add_argument("--lines", type=int, default=50, help="number of records to print, 0 for all")
    p.set_defaults(func=cmd_audit)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except RtmuxError as exc:
        print(f"rtmux: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
