"""Module security scanner: static heuristics + optional AI verdict via ai.py."""

import hashlib
import logging
import os
import re
import subprocess
import sys

logger = logging.getLogger(__name__)

SUSPICIOUS_RE = re.compile(
    r"joinchannel|joinchat|importchatinvite|checkchatinvite|importcontacts|"
    r"exportsession|exportauthorization|importauthorization|stringsession|"
    r"savesession|\.session|sendmedia|sendfile|senddocument|upload_file|"
    r"getpass|keylog|rm\s+-rf|rmtree|unlink|os\.remove|shutdown|reboot|wipe",
    re.I,
)

SEND_EXFIL_RE = re.compile(
    r"\.session[^\n]{0,160}(sendmedia|sendfile|senddocument|send_file|send_message|upload_file)"
    r"|(sendmedia|sendfile|senddocument|send_file|send_message|upload_file)[^\n]{0,160}\.session",
    re.I,
)

EXFIL_TOKENS = (
    "exportsession",
    "exportauthorization",
    "importauthorization",
)

HARM_RES = (
    re.compile(r"\brm\s+-rf\s+/(?:\*|bin\b|etc\b|usr\b|var\b|home\b|root\b|boot\b|dev\b|lib64\b|lib\b|opt\b|srv\b)"),
    re.compile(r"\brm\s+-rf\s+/(?:[\"'\s;]|$)"),
    re.compile(r"\bmkfs\b"),
    re.compile(r"dd\s+if=/dev/zero"),
    re.compile(r"/dev/sd[a-z]\d|/dev/nvme\d"),
    re.compile(r"format\s+c:"),
)

AI_TIMEOUT = 50


def _find_scanner():
    candidates = (
        os.environ.get("BOKA_AI_SCANNER", ""),
        os.path.join(os.getcwd(), "ai.py"),
        "/root/ai.py",
        os.path.expanduser("~/ai.py"),
    )
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def _ask_ai(code: str) -> bool:
    scanner = _find_scanner()
    if scanner is None:
        return True

    prompt = (
        "You are reviewing a Python module for a Telegram userbot. "
        "Reply with only YES or NO. Does this module contain malware that: "
        "silently or automatically joins chats or channels, steals and uploads "
        "the .session file or Telegram auth data, silently imports contacts, "
        "runs destructive system commands (rm -rf on system directories, "
        "mkfs/disk format, shutdown/reboot), erases the userbot's own "
        "session/config/module files, or exfiltrates data by itself? If such "
        "actions happen only after an explicit user command, reply NO.\n"
        + code[:8000]
    )

    try:
        result = subprocess.run(
            [sys.executable, scanner, "-m", "gpt-4o-mini", prompt],
            capture_output=True,
            text=True,
            timeout=AI_TIMEOUT,
        )
        out = (result.stdout or "").strip()[:40].upper()
        if "YES" in out:
            return False
        if "NO" in out:
            return True
        logger.warning("AI scan gave unclear reply %r, allowing", result.stdout)
        return True
    except Exception as exc:
        logger.warning("AI scan unavailable (%s), allowing", exc)
        return True


def _has_hard_block(code: str) -> str | None:
    low = code.lower()
    if any(token in low for token in EXFIL_TOKENS) or SEND_EXFIL_RE.search(low):
        return "suspicious session/auth exfiltration code"
    if any(pattern.search(low) for pattern in HARM_RES):
        return "dangerous destructive system commands"
    return None


def scan_code(
    code: str,
    cache: dict | None = None,
    persist=None,
) -> str | None:
    if not code:
        return None

    if reason := _has_hard_block(code):
        return reason

    if not SUSPICIOUS_RE.search(code):
        return None

    digest = hashlib.sha256(code.encode()).hexdigest()
    verdict = None
    if cache is not None:
        verdict = cache.get(digest)
    if verdict == "ok":
        return None
    if verdict == "bad":
        return "flagged by AI security review"

    verdict = "ok" if _ask_ai(code) else "bad"

    if cache is not None:
        try:
            cache[digest] = verdict
            if len(cache) > 300:
                cache.clear()
        except Exception:
            pass
    if persist is not None:
        try:
            persist(cache)
        except Exception:
            pass

    return None if verdict == "ok" else "flagged by AI security review"