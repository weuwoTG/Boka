# Part of the Boka Userbot local security subsystem.
# Implements a per-module Python sandbox applied to every third-party /
# non-core module before its source code is executed.

from __future__ import annotations

import builtins as _real_builtins
from builtins import __import__ as _real_import

from typing import Any


class ModuleSecurityError(Exception):
    """
    Raised when a sandboxed module tries to touch a blocked import or
    a blocked built-in (open/exec/eval/compile/...).
    """


DENIED_IMPORTS = {
    # --- OS / process / filesystem -----------------------------------------
    "os",
    "subprocess",
    "shutil",
    "ctypes",
    "multiprocessing",
    "shlex",
    "pty",
    "getpass",
    "grp",
    "pwd",
    "resource",
    "process",
    "signal",
    "statvfs",
    "posix",
    "posixpath",
    "winreg",
    "win32api",
    "win32process",
    "macpath",
    # --- raw networking -----------------------------------------------------
    "socket",
    "select",
    "selectors",
    "asyncore",
    "asynchat",
    # --- HTTP / client libraries -------------------------------------------
    "requests",
    "httpx",
    "aiohttp",
    "urllib",
    "urllib3",
    "http",
    "curl",
    "curl_cffi",
    "curlify",
    "wget",
    "webbrowser",
    "vf_wrapper",
    "gdown",
    "downloader",
    # --- named protocols ----------------------------------------------------
    "ftplib",
    "smtplib",
    "telnetlib",
    "poplib",
    "imaplib",
    "nntplib",
    "ssl",
    "dnspython",
    "dns",
    "asyncio_dns",
    "raw_socket",
    # --- alternative MTProto / DB clients (silent exfil) --------------------
    "pyrogram",
    "hydrogram",
    "gram2pyro",
    "telebank",
    "gramengine",
    "mtprotostatus",
    "pymongo",
    "asyncpg",
    "pymysql",
    "psycopg",
    "psycopg2",
    "redis",
    "aioredis",
    "cassandra",
    "kafka",
    "pika",
    "amqp",
    "sqlalchemy",
    # --- dynamic code execution / introspection ----------------------------
    "importlib",
    "pickle",
    "marshal",
    "shelve",
    "code",
    "codeop",
    "inspect",
    "gc",
    "runpy",
    "site",
    "zipapp",
    "builtins",
    # --- archive / file writers --------------------------------------------
    "zipfile",
    "tarfile",
    "tempfile",
    # --- misc system / info-leak surface -----------------------------------
    "sys",
    "platform",
    "pathlib",
    "personal_trace",
    # --- the Boka package itself (no reach-in to core/trusted code) ---------
    "boka",
    "boka_tl",
}

DANGEROUS_BUILTINS = {
    "open",
    "exec",
    "eval",
    "compile",
    "input",
    "breakpoint",
}

EXTRA_DENIED_ENV = "BOKA_SANDBOX_EXTRA"


def _deny(name: str):
    def _blocked(*_args, **_kwargs) -> Any:
        raise ModuleSecurityError(
            f"{name!r} is blocked by Boka local security (secure_local)"
        )

    return _blocked


def _restricted_import(
    name: str,
    globals: dict | None = None,  # noqa: A002
    locals: dict | None = None,  # noqa: A002
    fromlist: tuple = (),
    level: int = 0,
) -> Any:
    if level:
        raise ImportError(
            "relative imports are not allowed in sandboxed Boka modules"
        )

    base = name.split(".", maxsplit=1)[0]

    if base in DENIED_IMPORTS or base in _extra_denied():
        raise ImportError(
            f"Module {name!r} is blocked by Boka local security (secure_local)"
        )

    return _real_import(name, globals, locals, fromlist, level)


_EXTRA: frozenset[str] | None = None


def _extra_denied() -> frozenset[str]:
    global _EXTRA
    if _EXTRA is None:
        import os

        _EXTRA = frozenset(
            part.strip().lower()
            for part in os.environ.get(EXTRA_DENIED_ENV, "").split(",")
            if part.strip()
        )
    return _EXTRA


def make_sandbox_builtins() -> dict[str, Any]:
    """
    Build a replacement ``__builtins__`` mapping for a sandboxed module:
    all safe built-ins are kept, dangerous ones are stubbed out and
    ``__import__`` is swapped for the restricted import gate.
    """
    blocked = {
        name: _deny(name)
        for name in DANGEROUS_BUILTINS
        if hasattr(_real_builtins, name)
    }
    safe = {
        name: getattr(_real_builtins, name)
        for name in dir(_real_builtins)
        if not name.startswith("_") and name not in DANGEROUS_BUILTINS
    }
    safe["__import__"] = _restricted_import
    safe.update(blocked)
    return safe


def apply_sandbox(module: Any) -> None:
    """
    Lock the module's globals namespace before its body is executed.
    Called right before ``spec.loader.exec_module(module)``.
    """
    module.__builtins__ = make_sandbox_builtins()  # type: ignore[attr-defined]
    module.__boka_sandboxed__ = True  # type: ignore[attr-defined]


def finalize(module: Any) -> None:
    """
    Post-execution cleanup: drop anything that slipped into the module
    namespace and is not a legit part of a sandboxed module.
    """
    for name in DENIED_IMPORTS:
        module.__dict__.pop(name, None)
    module.__dict__["__builtins__"] = make_sandbox_builtins()