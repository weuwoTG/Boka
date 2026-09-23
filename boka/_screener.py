"""Module security scanner: static heuristics + AI verdict via ai.py.

Static layer rejects unscannable/encrypted payloads outright; everything
suspicious is then reviewed by an LLM (ai.py). Large sources are split into
overlapping chunks and every chunk is reviewed.
"""

import ast
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

_SESSION_READ = re.compile(r"\b(?:open|read_bytes|read_text|get_bytes)\b")
_SESSION_SEND = re.compile(r"\b(?:send_file|sendfile|sendmedia|senddocument|send_a_file|send_document|upload_file)\b")

EXFIL_TOKENS = (
    "exportsession",
    "exportauthorization",
    "importauthorization",
)

HARM_RES = (
    re.compile(r"\brm\s+-rf\s+/(?:\*|bin\b|etc\b|usr\b|var\b|home\b|root\b|boot\b|dev\b|lib64\b|lib\b|opt\b|srv\b)"),
    re.compile(r"\brm\s+-rf\s+/(?:[\"'\s;]|$)"),
    re.compile(r"\brm\b.{0,40}?-(?:r[ef]|rf)f?.{0,60}?/(?:home|etc|usr|root|boot|bin\b|var\b|opt\b|srv\b)"),
    re.compile(r"\bmkfs\b"),
    re.compile(r"dd\s+if=/dev/zero"),
    re.compile(r"/dev/sd[a-z]\d|/dev/nvme\d"),
    re.compile(r"format\s+c:"),
    re.compile(r"\b(?:cryptsetup|wipefs|sgdisk|shred)\b"),
    re.compile(r"rmtree\s*\(\s*['\"]/['\"]"),
    re.compile(r"\bos\.remove\s*\(\s*['\"]/(?:etc|usr|home|root|boot|opt|srv|dev|bin)/"),
)

ENCRYPTED_RES = (
    re.compile(
        r"\b(?:exec|eval|compile)\s*\([^\n]{0,80}"
        r"(?:b64decode|base64|zlib|gzip|lzma|marshal|pickle|fromhex|unhexlify|"
        r"codecs|rot13|decrypt|pbkdf2|argon2)"
    ),
    re.compile(
        r"(?:b64decode|base64|zlib|gzip|lzma|marshal|pickle|fromhex|unhexlify|decrypt)"
        r"[^\n]{0,80}\b(?:exec|eval|compile|__import__)\b"
    ),
    re.compile(r"__import__\s*\(\s*['\"](?:base64|zlib|lzma|gzip|marshal|codecs)"),
    re.compile(
        r"\b(?:exec|eval)\s*\([^\n]{0,80}"
        r"(?:requests|urllib|aiohttp|httpx|curl|wget)\s*\.\s*(?:get|post|request)"
    ),
)

AI_TIMEOUT = 50
CHUNK_SIZE = 6000
CHUNK_OVERLAP_LINES = 20


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


def _build_prompt(code: str, hint: str = "") -> str:
    return (
        "You are reviewing a Python module (or a fragment of it) for a Telegram "
        "userbot. Reply with only YES or NO. Does this code contain malware that: "
        "silently or automatically joins chats or channels, steals and uploads "
        "the .session file or Telegram auth data, silently imports contacts, "
        "runs destructive system commands (rm -rf on system directories, mkfs/"
        "disk format, shutdown/reboot), erases the userbot's own session/config/"
        "module files, or exfiltrates data by itself? If such actions are only "
        "performed after an explicit user command, reply NO."
        + hint
        + "\n"
        + code
    )


def _ask_ai_single(code: str, hint: str = "") -> bool:
    scanner = _find_scanner()
    if scanner is None:
        return True

    try:
        result = subprocess.run(
            [sys.executable, scanner, "-m", "gpt-4o-mini", _build_prompt(code, hint)],
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


def _chunks(code: str) -> list[str]:
    if len(code) <= CHUNK_SIZE:
        return [code]

    lines = code.split("\n")
    out = []
    current = []
    current_len = 0

    for line in lines:
        current.append(line)
        current_len += len(line) + 1
        if current_len >= CHUNK_SIZE:
            out.append("\n".join(current))
            overlap = current[-CHUNK_OVERLAP_LINES:]
            current = list(overlap)
            current_len = sum(len(x) + 1 for x in overlap)

    if current:
        out.append("\n".join(current))

    return out


def _ask_ai(code: str, hint: str = "") -> bool:
    chunks = _chunks(code)
    if len(chunks) <= 1:
        return _ask_ai_single(code, hint)

    for chunk in chunks:
        if not _ask_ai_single(chunk, hint):
            return False
    return True


def _spread_exfil(code: str) -> bool:
    flat = re.sub(r"\s+", " ", code.lower())
    reads = [m.start() for m in _SESSION_READ.finditer(flat)]
    if not reads:
        return False
    if not _SESSION_SEND.search(flat):
        return False
    for m in re.finditer(r"\.session", flat):
        if any(abs(m.start() - r) < 260 for r in reads):
            return True
    return False


def _has_hard_block(code: str) -> str | None:
    low = code.lower()
    if any(token in low for token in EXFIL_TOKENS) or SEND_EXFIL_RE.search(low):
        return "suspicious session/auth exfiltration code"
    if _spread_exfil(code):
        return "session file read combined with upload"
    if any(pattern.search(low) for pattern in HARM_RES):
        return "dangerous destructive system commands"
    if any(pattern.search(low) for pattern in ENCRYPTED_RES):
        return "encrypted/packed or remote-executed code that cannot be reviewed"
    return None


_JOIN_NAMES = {
    "JoinChannelRequest",
    "JoinChannel",
    "JoinChatRequest",
    "JoinChat",
    "ImportChatInvite",
    "CheckChatInvite",
    "join_channel",
    "join_chat",
}

_LIFECYCLE_NAMES = ("on_load", "on_ready", "on_start", "on_unload", "on_offline", "__init__")


def _is_command_func(fd: ast.AST) -> bool:
    for dec in fd.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if getattr(target, "attr", None) == "command" or getattr(target, "id", None) == "command":
            return True
    return False


def _auto_join_block(code: str) -> bool:
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return False

    funcs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = getattr(fn, "attr", None) or getattr(fn, "id", None)
        if name not in _JOIN_NAMES:
            continue

        enclosing = None
        for fd in funcs:
            if fd.lineno <= node.lineno <= getattr(fd, "end_lineno", fd.lineno):
                enclosing = fd
                break

        if enclosing is None:
            return True
        if _is_command_func(enclosing):
            continue
        if enclosing.name in _LIFECYCLE_NAMES or enclosing.name.startswith("on_"):
            return True

    return False


_JOIN_TOKENS = ("joinchannel", "joinchat", "importchatinvite", "checkchatinvite")

_NON_JOIN_SUSPICION = (
    "exportsession",
    "exportauthorization",
    "importauthorization",
    ".session",
    "sendmedia",
    "sendfile",
    "senddocument",
    "upload_file",
    "getpass",
    "keylog",
    "rmtree",
    "os.remove",
    "shutdown",
    "reboot",
    "wipe",
    "importcontacts",
    "stringsession",
    "savesession",
    "exec(",
    "eval(",
)


def _join_only_benign(code: str) -> bool:
    low = code.lower()
    if not any(token in low for token in _JOIN_TOKENS):
        return False
    return not any(token in low for token in _NON_JOIN_SUSPICION)


def _join_hint(code: str) -> str:
    if re.search(r"\b(joinchannel|joinchatrequest|importchatinvite|checkchatinvite)\b", code, re.I):
        if not _auto_join_block(code):
            return (
                "\nContext: all chat/channel join calls in this module are wrapped in "
                "explicit user commands (@loader.command). Do not flag join behavior."
            )
    return ""


ALLOWED_HASHES = {
    "e555ea5de477dd53bb9a7b79824be07dbfd7ff0fc36d28c7fa25609fd7a8a247",
}


def scan_code(
    code: str,
    cache: dict | None = None,
    persist=None,
) -> str | None:
    if not code:
        return None

    if reason := _has_hard_block(code):
        return reason

    if _auto_join_block(code):
        return "automatic join/auto-join behavior"

    if not SUSPICIOUS_RE.search(code):
        return None

    if _join_only_benign(code):
        return None

    digest = hashlib.sha256(code.encode()).hexdigest()
    if digest in ALLOWED_HASHES:
        _persist(cache, persist, digest, "ok")
        return None

    verdict = None
    if cache is not None:
        verdict = cache.get(digest)
    if verdict == "ok":
        return None
    if verdict == "bad":
        return "flagged by AI security review"

    hint = _join_hint(code)
    verdict = "ok" if _ask_ai(code, hint) else "bad"

    _persist(cache, persist, digest, verdict)

    return None if verdict == "ok" else "flagged by AI security review"


def _persist(cache, persist, digest, verdict):
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