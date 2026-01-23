"""
Terminal Service - Manages PTY processes for web terminal.
"""
import os
import select
from typing import Optional

import ptyprocess


_sessions: dict[str, ptyprocess.PtyProcess] = {}


def create_session(session_id: str, shell: str = "/bin/bash") -> bool:
    if session_id in _sessions:
        return False

    try:
        home = os.path.expanduser("~")

        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env["HOME"] = home

        process = ptyprocess.PtyProcess.spawn(
            [shell],
            cwd=home,
            env=env,
            dimensions=(24, 80),
        )

        _sessions[session_id] = process
        print(f"[Terminal] Session {session_id} created")
        return True
    except Exception as e:
        print(f"[Terminal] Failed to create session: {e}")
        return False


def get_session(session_id: str) -> Optional[ptyprocess.PtyProcess]:
    return _sessions.get(session_id)


def write_to_session(session_id: str, data: str) -> bool:
    session = _sessions.get(session_id)
    if not session:
        return False

    try:
        session.write(data.encode("utf-8"))
        return True
    except Exception as e:
        print(f"[Terminal] Write error: {e}")
        return False


def read_from_session(session_id: str, timeout: float = 0.1) -> Optional[str]:
    session = _sessions.get(session_id)
    if not session:
        return None

    try:
        ready, _, _ = select.select([session.fd], [], [], timeout)
        if ready:
            data = session.read(1024)
            return data.decode("utf-8", errors="replace")
        return ""
    except EOFError:
        return None
    except Exception as e:
        print(f"[Terminal] Read error: {e}")
        return None


def resize_session(session_id: str, rows: int, cols: int) -> bool:
    session = _sessions.get(session_id)
    if not session:
        return False

    try:
        session.setwinsize(rows, cols)
        return True
    except Exception as e:
        print(f"[Terminal] Resize error: {e}")
        return False


def close_session(session_id: str) -> bool:
    session = _sessions.pop(session_id, None)
    if not session:
        return False

    try:
        if session.isalive():
            session.terminate(force=True)
        print(f"[Terminal] Session {session_id} closed")
        return True
    except Exception as e:
        print(f"[Terminal] Close error: {e}")
        return False


def is_session_alive(session_id: str) -> bool:
    session = _sessions.get(session_id)
    if not session:
        return False
    return session.isalive()


def list_sessions() -> list[str]:
    return list(_sessions.keys())
