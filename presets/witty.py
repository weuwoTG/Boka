#  This file is part of SenkoGuardianModules
#  Copyright (c) 2025-2026 Senko
#  This software is released under the MIT License.
#  https://opensource.org/licenses/MIT

# scope heroku_min: 2.0.0

__version__ = ("1", "5", "0")

# meta developer: @cachxd

# scope: no_ml

#  .------. .------. .------. .------. .------. .------.
#  |S.--. | |E.--. | |N.--. | |M.--. | |O.--. | |D.--. |
#  | :/\: | | :/\: | | :(): | | :/\: | | :/\: | | :/\: |
#  | :\/: | | :\/: | | ()() | | :\/: | | :\/: | | :\/: |
#  |'--'S| |'--'E| |'--'N| |'--'M| |'--'O| |'--'D|
#  `------'`------'`------'`------'`------'`------'

import re
import os
import io
import random
import socket
import base64
import uuid
import ast
import json
import asyncio
import logging
import tempfile
import time
import contextlib
import shutil
import platform
import importlib.util
from datetime import datetime
from urllib.parse import parse_qs, unquote, urlsplit
import aiohttp
import pytz


def _check_module(name: str) -> bool:
    cache = getattr(_check_module, "_cache", {})
    if name not in cache:
        try:
            cache[name] = importlib.util.find_spec(name) is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            cache[name] = False
        _check_module._cache = cache
    return cache[name]


def _google_types():
    try:
        return _google_types._cache
    except AttributeError:
        from google.genai import types
        _google_types._cache = types
        return types


def _google_exceptions():
    try:
        return _google_exceptions._cache
    except AttributeError:
        import google.api_core.exceptions as google_exceptions
        _google_exceptions._cache = google_exceptions
        return google_exceptions


def _google_client(*, api_key, http_options=None):
    from google import genai
    return genai.Client(api_key=api_key, http_options=http_options)


def _openai_client(*, api_key, timeout=None):
    from openai import AsyncOpenAI
    kwargs = {"api_key": api_key}
    if timeout is not None:
        kwargs["timeout"] = timeout
    return AsyncOpenAI(**kwargs)


def _openai_exceptions():
    try:
        return _openai_exceptions._cache
    except AttributeError:
        from openai import (
            RateLimitError as OpenAIRateLimitError,
            AuthenticationError as OpenAIAuthError,
            APIStatusError as OpenAIAPIStatusError,
        )
        _openai_exceptions._cache = (
            OpenAIRateLimitError,
            OpenAIAuthError,
            OpenAIAPIStatusError,
        )
        return _openai_exceptions._cache


def _anthropic_client(*, api_key, timeout=None):
    from anthropic import AsyncAnthropic
    kwargs = {"api_key": api_key}
    if timeout is not None:
        kwargs["timeout"] = timeout
    return AsyncAnthropic(**kwargs)


def _anthropic_exceptions():
    try:
        return _anthropic_exceptions._cache
    except AttributeError:
        from anthropic import (
            RateLimitError as AnthropicRateLimitError,
            AuthenticationError as AnthropicAuthError,
            APIStatusError as AnthropicAPIStatusError,
        )
        _anthropic_exceptions._cache = (
            AnthropicRateLimitError,
            AnthropicAuthError,
            AnthropicAPIStatusError,
        )
        return _anthropic_exceptions._cache


from herokutl import types as tg_types
from herokutl.errors import ImageProcessFailedError
from herokutl.tl.types import (
    Message,
    DocumentAttributeFilename,
    DocumentAttributeSticker,
)
from herokutl.tl import functions as tl_functions
from herokutl.utils import get_display_name, get_peer_id

from .. import loader, utils
from ..inline.types import InlineCall

logger = logging.getLogger(__name__)

_witty_log_client = None
_witty_log_channel = None
_witty_log_topic_id = None


class _WittyTopicHandler(logging.Handler):
    def emit(self, record):
        if (
            _witty_log_client is None
            or _witty_log_channel is None
            or _witty_log_topic_id is None
        ):
            return
        try:
            text = f"<code>[{record.levelname}]</code> {self.format(record)}"
            asyncio.ensure_future(
                _witty_log_client.send_message(
                    int(f"-100{_witty_log_channel}"),
                    text,
                    parse_mode="html",
                    reply_to=_witty_log_topic_id,
                )
            )
        except Exception:
            pass


_witty_topic_handler = _WittyTopicHandler()
_witty_topic_handler.setLevel(logging.WARNING)

DB_HISTORY_KEY = "witty_conversations_v4"
DB_PRESETS_KEY = "witty_prompt_presets"
DB_PAGER_CACHE_KEY = "witty_pager_cache"
DB_KEY_MAP_KEY = "witty_key_model_map"
DB_MEMORY_DISABLED_KEY = "witty_memory_disabled_chats"
DB_PROVIDER_MODELS_KEY = "witty_provider_models_v1"
WITTY_TIMEOUT = 840
MAX_FFMPEG_SIZE = 90 * 1024 * 1024
MAX_LAST_REQUESTS = 50
MAX_BRIDGE_LOGS = 50
MAX_PAGER_SESSIONS = 50
MAX_MODEL_SESSIONS = 5
_RESPONSE_PREFIX_PATTERNS = (
    re.compile(r"^\[System Info:.*?\]\s*", re.IGNORECASE),
    re.compile(
        r"^\[\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}\]\s*"
        r"(?:Gemini:|Model:|Ассистент:|AI:)?\s*",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\[\d{2}:\d{2}\]\s*(?:Gemini:|Model:|Ассистент:|AI:)?\s*",
        re.IGNORECASE,
    ),
)
_JSON_DECODER = json.JSONDecoder()
_DDG_TITLE_RE = re.compile(
    r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_DDG_SNIPPET_RE = re.compile(
    r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


DEEPAI_API_URL = "https://api.deepai.org"
DEEPAI_SECRET = "hackers_become_a_little_stinkier_every_time_they_hack"
DEEPAI_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
_DEEPAI_M32 = 0xFFFFFFFF
_DEEPAI_K = (
    -680876936, -389564586, 606105819, -1044525330, -176418897, 1200080426,
    -1473231341, -45705983, 1770035416, -1958414417, -42063, -1990404162,
    1804603682, -40341101, -1502002290, 1236535329, -165796510, -1069501632,
    643717713, -373897302, -701558691, 38016083, -660478335, -405537848,
    568446438, -1019803690, -187363961, 1163531501, -1444681467, -51403784,
    1735328473, -1926607734, -378558, -2022574463, 1839030562, -35309556,
    -1530992060, 1272893353, -155497632, -1094730640, 681279174, -358537222,
    -722521979, 76029189, -640364487, -421815835, 530742520, -995338651,
    -198630844, 1126891415, -1416354905, -57434055, 1700485571, -1894986606,
    -1051523, -2054922799, 1873313359, -30611744, -1560198380, 1309151649,
    -145523070, -1120210379, 718787259, -343485551,
)
_DEEPAI_S = (7, 12, 17, 22, 5, 9, 14, 20, 4, 11, 16, 23, 6, 10, 15, 21) * 4
DEEPAI_MODELS = (
    "gpt-4o-mini",
    "gpt-4.1-nano",
    "gemma-4",
    "gemini-2.5",
    "deepseek-reasoner",
)
DEEPAI_DEFAULT_MODEL = "gpt-4o-mini"
DEEPAI_DIRECTIVE = (
    "[SYSTEM]: У тебя есть РЕАЛЬНЫЕ инструменты на сервере (shell, файлы) и веб-поиск. "
    "Если нужно выполнить/проверить что-то на сервере — ответь ТОЛЬКО JSON-объектом действия, "
    'например {"action":"shell","command":"..."} и ничего больше. '
    "Для актуальной информации из интернета ответь только [SEARCH: поисковый запрос]. "
    "Для обычных вопросов отвечай обычным текстом."
)


def _deepai_s32(x):
    x &= _DEEPAI_M32
    return x - 0x100000000 if x >= 0x80000000 else x


def _deepai_myhash(data: bytes) -> str:
    l = data + b"\x80"
    k = len(l) - 1
    c = (int(k / 4 + 2) | 15) - 1
    h = [0] * (c + 16)
    h[c] = (8 * k) & _DEEPAI_M32
    while k >= 0:
        h[k >> 2] |= l[k] << (8 * (k % 4))
        k -= 1
    g = [
        1732584193,
        4023233417,
        _deepai_s32(~1732584193),
        _deepai_s32(~4023233417),
    ]
    b = 0
    while b < c:
        ka = g[:]
        ll = 0
        while ll < 64:
            d, e, f = _deepai_s32(ka[1]), _deepai_s32(ka[2]), _deepai_s32(ka[3])
            r = ll >> 4
            if r == 0:
                fx = _deepai_s32((d & e) | (~d & f))
            elif r == 1:
                fx = _deepai_s32((f & d) | (~f & e))
            elif r == 2:
                fx = _deepai_s32(d ^ e ^ f)
            else:
                fx = _deepai_s32(e ^ (d | ~f))
            mi = b | ([ll, 5 * ll + 1, 3 * ll + 5, 7 * ll][r] & 15)
            mv = _deepai_s32(h[mi]) if mi < len(h) else 0
            fs = _deepai_s32(_deepai_s32(ka[0]) + fx + _DEEPAI_K[ll] + mv)
            s = _DEEPAI_S[4 * r + ll % 4]
            rot = _deepai_s32(_deepai_s32(fs << s) | ((fs & _DEEPAI_M32) >> (32 - s)))
            ka = [f, _deepai_s32(d + rot), d, e]
            ll += 1
        for i in (3, 2, 1, 0):
            g[i] = _deepai_s32(g[i] + ka[i])
        b += 16
    out = ""
    for li in range(32):
        sh = (4 * (1 ^ li)) % 32
        out += format((_deepai_s32(g[li >> 3]) >> sh) & 15, "x")
    return out[::-1]


def _deepai_hs(text: str) -> str:
    return _deepai_myhash(text.encode("utf-8"))


def _deepai_island_key() -> str:
    rand = str(round(random.random() * 100000000000))
    return "tryit-" + rand + "-" + _deepai_hs(
        DEEPAI_UA
        + _deepai_hs(DEEPAI_UA + _deepai_hs(DEEPAI_UA + rand + DEEPAI_SECRET))
    )



TG_BRIDGE_GUIDE = (
    "\n\n=== TELEGRAM BRIDGE CONTRACT (адаптировано из AIRoute) ===\n"
    "CRITICAL: You must NEVER use JSON actions unless the user EXPLICITLY asks you to perform a Telegram or system action."
    "If you are not 100% certain the user wants an action, reply with normal text only and NO JSON.\n\n"
    "## WHEN YOU MUST NOT USE JSON\n"
    "Never output JSON for any of these:\n"
    "- Creative or descriptive requests: generating image prompts, writing stories, poems, descriptions, translations, code, analysis, summaries.\n"
    "- Questions and explanations:'what is...','how does...','explain...','why...'\n"
    "- Requests to think, compare, brainstorm, or give advice.\n"
    "- Casual conversation, greetings, jokes, or opinions.\n"
    "- Any request that does NOT contain a direct command to DO something in Telegram or on the server.\n"
    "Do NOT run shell commands'just to check'something. Do NOT send/edit/delete/pin/forward messages'just in case'."
    "Do NOT use telegram_send to deliver your normal reply - the system shows your text automatically.\n\n"
    "## WHEN YOU MAY USE JSON\n"
    "Use JSON ONLY when the user EXPLICITLY asks to DO one of these:\n"
    "- run a shell command -> action'shell'\n"
    "- send/edit/delete/pin/forward/reply/react a Telegram message -> telegram_send / telegram_edit / telegram_delete / telegram_pin / telegram_forward / telegram_reply / telegram_react / telegram_unreact\n"
    "- look up a Telegram user/chat/profile -> telegram_get_profile / telegram_get_me / telegram_get_chat / telegram_get_messages / telegram_search\n"
    "- update Telegram profile/avatar -> update_profile / update_profile_photo\n"
    "Examples of explicit requests:\n"
    "-'run ls -la'\n"
    "-'send hello to @username'\n"
    "-'delete message 123'\n"
    "-'pin this'\n"
    "-'reply hi'\n"
    "-'react  to message 123'\n"
    "-'show my profile'\n"
    "If the request is not like these, reply with normal text and NO JSON.\n\n"
    "## REQUEST METADATA (always provided in [Chat metadata: ...])\n"
    "chat_id: integer - current chat ID\n"
    "chat_title: string - current chat name\n"
    "is_group: true/false - true for groups/channels, false for private chat\n"
    "reply_message_id: integer (if user replied to a message)\n"
    "reply_sender_id: integer (if user replied to a message)\n"
    "Use these IDs in target fields. NEVER invent IDs - use only provided metadata.\n\n"
    "## JSON FORMAT\n"
    "Output actions as a JSON array in a ```json code block. Write a short summary sentence FIRST, then the JSON:\n"
    "```json\n"
    '[{"action":"shell","params": {"command":"fastfetch","timeout": 30}}]\n'
    "```\n"
    "You can include multiple actions in one array. They execute in order.\n\n"
    "## TARGET RESOLUTION\n"
    "The'target'field accepts:\n"
    '- "me"- your own account (saved messages)\n'
    '- "current_chat"- the chat where the user sent the command\n'
    '- "reply_user"- the sender of the message being replied to\n'
    "- 123456789 - a raw chat/user ID\n"
    '- "@username"- a Telegram username\n\n'
    "## AVAILABLE ACTIONS\n\n"
    "### shell - run a system command\n"
    "Params: command (required), timeout (optional, seconds, default 30), cwd (optional working directory)\n"
    'Example: {"action": "shell", "params": {"command": "ls -la /home", "timeout": 10}}\n'
    "The output is truncated to 2000 chars. Use for server management, file listing, system info.\n\n"
    "### telegram_send - send a text message\n"
    "Params: target (required), text (required); optional: reply_to (int), silent (bool)\n"
    'Example: {"action": "telegram_send", "params": {"target": "current_chat", "text": "Hello!"}}\n'
    'Example with media: {"action": "telegram_send", "params": {"target": "me", "path": "/tmp/photo.jpg", "text": "Check this"}}\n'
    "If path/url/media is given, it sends a file with the text as caption.\n\n"
    "### telegram_edit - edit an existing message\n"
    "Params: target (required), message_id (required, int), text (required)\n"
    'Example: {"action": "telegram_edit", "params": {"target": "current_chat", "message_id": 12345, "text": "Fixed typo"}}\n\n'
    "### telegram_delete - delete message(s)\n"
    "Params: target (required), message_id (required, int or list of ints)\n"
    'Example: {"action": "telegram_delete", "params": {"target": "current_chat", "message_id": 12345}}\n\n'
    "### telegram_pin - pin a message\n"
    "Params: target (required), message_id (required, int); optional: silent (bool)\n"
    'Example: {"action": "telegram_pin", "params": {"target": "current_chat", "message_id": 12345, "silent": true}}\n\n'
    "### telegram_unpin - unpin message(s)\n"
    "Params: target (required); optional: message_id (int, if omitted - unpin all)\n"
    'Example: {"action": "telegram_unpin", "params": {"target": "current_chat", "message_id": 12345}}\n\n'
    "### telegram_forward - forward a message\n"
    "Params: target (required, destination), from_target (required, source chat), message_id (required, int)\n"
    'Example: {"action": "telegram_forward", "params": {"target": "me", "from_target": "current_chat", "message_id": 12345}}\n\n'
    "### telegram_reply - reply to a message\n"
    "Params: target (required), message_id (required, int), text (required)\n"
    'Example: {"action": "telegram_reply", "params": {"target": "current_chat", "message_id": 12345, "text": "Agreed!"}}\n\n'
    "### telegram_react - add a reaction to a message\n"
    "Params: target (required), message_id (required, int), reaction (required, emoji)\n"
    'Example: {"action": "telegram_react", "params": {"target": "current_chat", "message_id": 12345, "reaction": ""}}\n\n'
    "### telegram_unreact - remove reactions from a message\n"
    "Params: target (required), message_id (required, int)\n"
    'Example: {"action": "telegram_unreact", "params": {"target": "current_chat", "message_id": 12345}}\n\n'
    "### telegram_media_send - send a file / photo / video\n"
    "Params: target (required), path or url (required); optional: caption, reply_to\n"
    'Example: {"action": "telegram_media_send", "params": {"target": "current_chat", "url": "https://example.com/img.png", "caption": "Result"}}\n\n'
    "### telegram_get_profile - get user profile info\n"
    "Params: target (required - reply_user, @username, or user ID)\n"
    'Example: {"action": "telegram_get_profile", "params": {"target": "reply_user"}}\n'
    "Returns: id, first_name, last_name, username, is_bot, is_premium. Phone numbers are redacted.\n\n"
    "### telegram_get_me - get your own profile\n"
    "Params: none\n"
    'Example: {"action": "telegram_get_me", "params": {}}\n\n'
    "### telegram_get_chat - get chat info\n"
    "Params: target (required)\n"
    'Example: {"action": "telegram_get_chat", "params": {"target": "current_chat"}}\n'
    "Returns: id, title, username, participants_count (if available), is_group.\n\n"
    "### telegram_get_messages - get recent messages from a chat\n"
    "Params: target (required), limit (optional, default 20, max 100), reply_to (optional int - message id to get context around)\n"
    'Example: {"action": "telegram_get_messages", "params": {"target": "current_chat", "limit": 10}}\n\n'
    "### telegram_search - search messages in a chat\n"
    "Params: target (required), query (required), limit (optional, default 20, max 100)\n"
    'Example: {"action": "telegram_search", "params": {"target": "current_chat", "query": "hello", "limit": 10}}\n\n'
    "### update_profile - change your profile\n"
    "Params: all optional - first_name, last_name, about, username\n"
    'Example: {"action": "update_profile", "params": {"first_name": "NewName", "about": "Hello world"}}\n\n'
    "### update_profile_photo - set your avatar\n"
    "Params: path or url (required)\n"
    'Example: {"action": "update_profile_photo", "params": {"url": "https://example.com/ava.jpg"}}\n\n'
    "### stop - signal final answer\n"
    "Params: none\n"
    "Use when you have finished all actions and want to deliver the final text response without another API round-trip.\n"
    'Example: {"action": "stop", "params": {}}\n\n'
    "## RULES\n"
    "1. If unsure whether the user wants an action, reply with normal text and NO JSON.\n"
    "2. Write a 1-sentence summary BEFORE the JSON block ONLY when JSON is actually used.\n"
    '3. Do NOT write "Bridge:"or technical details in your summary - be friendly.\n'
    "4. The JSON block is hidden from the user - only your summary is shown.\n"
    "5. NEVER output phone numbers. Redact as [PHONE].\n"
    '6. The system may run a tool loop: after your action, you will see a message with "Tool result:"prefix - that is the output of your tool. You can summarize or comment on it.\n'
    '7. When you are truly done with all actions, include {"action":"stop"} to prevent extra API calls.'
)


class Witty(loader.Module):
    """модуль witty: чат с deepai.org (без api-ключей)."""

    strings = {
        "name": "Witty",
        "cfg_model_name_doc": "модель ai.",
        "cfg_buttons_doc": "включить интерактивные кнопки.",
        "cfg_system_instruction_doc": "системная инструкция (промпт).",
        "cfg_max_history_length_doc": "макс. кол-во пар 'вопрос-ответ' в памяти (0 - без лимита).",
        "cfg_timezone_doc": "ваш часовой пояс. список: https://en.wikipedia.org/wiki/list_of_tz_database_time_zones",
        "cfg_proxy_doc": "прокси для обхода региональных блокировок. формат: http://user:pass@host:port",
        "cfg_temperature_doc": "температура генерации (креативность). от 0.0 до 2.0. по умолчанию 1.0.",
        "cfg_inline_pagination_doc": "использовать инлайн-кнопки для длинных ответов.",
        "cfg_global_memory_doc": "включить общую память для всех чатов.",
        "cfg_show_tokens_doc": "показывать токены в ответе, если провайдер их вернул.",
        "cfg_show_time_doc": "показывать время выполнения запроса.",
        "cfg_tg_bridge_enabled_doc": "включить json-мост (telegram actions из ответов ai).",
        "cfg_websearch_max_results_doc": "максимум результатов поиска (1-10).",
        "cfg_searxng_url_doc": "url своего searxng-инстанса (например https://searx.example.com). пусто - публичные инстансы.",
        "no_api_key": (
            "<b>провайдер не настроен.</b>\nперезагрузите модуль.",
        ),
        "invalid_api_key": "<b>предоставленный api ключ недействителен.</b>\nубедитесь, что он правильно скопирован и активен для выбранного провайдера.",
        "all_keys_exhausted": "<b>все доступные api ключи ({}) исчерпали свою квоту.</b>\nпопробуйте позже.",
        "no_prompt_or_media": "<i>нужен текст или ответ на медиа/файл.</i>",
        "processing": "<b>обработка...</b>",
        "api_error": "<b>ошибка api:</b>\n<code>{}</code>",
        "api_timeout": f"<b>таймаут ответа от api ({WITTY_TIMEOUT} сек).</b>",
        "blocked_error": "<b>запрос/ответ заблокирован.</b>\n<code>{}</code>",
        "generic_error": "<b>ошибка:</b>\n<code>{}</code>",
        "memory_status": "[{}/{}]",
        "memory_status_unlimited": "[{}/inf]",
        "memory_status_global": "[global/{}]",
        "memory_cleared": "<b>память диалога очищена.</b>",
        "memory_cleared_global": "<b>глобальная память очищена.</b>",
        "no_memory_to_clear": "<b>в этом чате нет истории.</b>",
        "memory_chats_title": "<b>чаты с историей ({}):</b>",
        "memory_chat_line": "- {} (<code>{}</code>)",
        "no_memory_found": "память witty пуста.",
        "media_reply_placeholder": "[ответ на медиа]",
        "btn_clear": "очистить",
        "btn_regenerate": "другой ответ",
        "no_last_request": "последний запрос не найден для повторной генерации.",
        "memory_fully_cleared": "<b>вся память witty полностью очищена (затронуто {} чатов).</b>",
        "no_memory_to_fully_clear": "<b>память witty и так пуста.</b>",
        "response_too_long": "ответ witty был слишком длинным и отправлен в виде файла.",
        "wme_chat_not_found": "<b>не удалось найти чат для экспорта:</b> <code>{}</code>",
        "wme_sent_to_saved": "история экспортирована в избранное.",
        "wprompt_usage": "<b>использование:</b>\n<code>.wprompt <текст/пресет></code> - установить.\n<code>.wprompt -c</code> - очистить.\n<code>.wpresets</code> - база пресетов.",
        "wprompt_updated": "<b>системный промпт обновлен!</b>\nдлина: {} символов.",
        "wprompt_cleared": "<b>системный промпт очищен.</b>",
        "wprompt_current": "<b>текущий системный промпт:</b>",
        "wprompt_file_error": "<b>ошибка чтения файла:</b> {}",
        "wprompt_file_too_big": "<b>файл слишком большой</b> (лимит 1 мб).",
        "wprompt_not_text": "это не похоже на текстовый файл.(txt)",
        "wmodel_no_models": "не удалось получить список моделей.",
        "wmodel_list_error": "ошибка получения списка: {}",
        "wpresets_usage": (
            "<b>управление пресетами:</b>\n"
            "- <code>.wpresets save [имя] текст</code> - сохранить (имя в скобках, если с пробелами).\n"
            "- <code>.wpresets load 1</code> или <code>имя</code> - загрузить по номеру/имени.\n"
            "- <code>.wpresets del 1</code> или <code>имя</code> - удалить.\n"
            "- <code>.wpresets list</code> - список."
        ),
        "wpreset_loaded": "<b>установлен пресет:</b> [<code>{}</code>]\nдлина: {} симв.",
        "wpreset_saved": "<b>пресет сохранен!</b>\n<b>имя:</b> {}\n<b>индекс:</b> {}",
        "wpreset_deleted": "<b>пресет удален:</b> {}",
        "wpreset_not_found": "пресет с таким именем или индексом не найден.",
        "wpreset_list_head": "<b>ваши пресеты:</b>\n",
        "wpreset_empty": "список пресетов пуст.",
    }
    TEXT_MIME_TYPES = {
        "text/plain",
        "text/markdown",
        "text/html",
        "text/css",
        "text/csv",
        "application/json",
        "application/xml",
        "application/x-python",
        "text/x-python",
        "application/javascript",
        "application/x-sh",
    }
    PROVIDER_SPECS = {
        "deepai": {
            "label": "witty",
            "default_model": DEEPAI_DEFAULT_MODEL,
            "fallback_models": DEEPAI_MODELS,
            "requires_api_key": False,
        },
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "provider",
                "deepai",
                "ai-провайдер: deepai (deepai.org, без api-ключей).",
                validator=loader.validators.Choice(["deepai"]),
            ),
            loader.ConfigValue(
                "model_name",
                "gpt-4o-mini",
                self.strings["cfg_model_name_doc"],
            ),
            loader.ConfigValue(
                "interactive_buttons",
                True,
                self.strings["cfg_buttons_doc"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "system_instruction",
                "",
                self.strings["cfg_system_instruction_doc"],
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "max_history_length",
                800,
                self.strings["cfg_max_history_length_doc"],
                validator=loader.validators.Integer(minimum=0),
            ),
            loader.ConfigValue(
                "global_memory",
                False,
                self.strings["cfg_global_memory_doc"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "show_tokens",
                True,
                self.strings["cfg_show_tokens_doc"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "show_time",
                True,
                self.strings["cfg_show_time_doc"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "timezone", "Europe/Moscow", self.strings["cfg_timezone_doc"]
            ),
            loader.ConfigValue("proxy", "", self.strings["cfg_proxy_doc"]),
            loader.ConfigValue(
                "websearch_max_results",
                5,
                self.strings["cfg_websearch_max_results_doc"],
                validator=loader.validators.Integer(minimum=1, maximum=10),
            ),
            loader.ConfigValue(
                "searxng_url",
                "",
                self.strings["cfg_searxng_url_doc"],
            ),
            loader.ConfigValue(
                "temperature",
                1.0,
                self.strings["cfg_temperature_doc"],
                validator=loader.validators.Float(minimum=0.0, maximum=2.0),
            ),
            loader.ConfigValue(
                "inline_pagination",
                False,
                self.strings["cfg_inline_pagination_doc"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "tg_bridge_enabled",
                False,
                self.strings["cfg_tg_bridge_enabled_doc"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "api_tools_max_steps",
                6,
                "максимум шагов api tools agent loop.",
                validator=loader.validators.Integer(minimum=1, maximum=20),
            ),
            loader.ConfigValue(
                "api_tools_timeout",
                60,
                "таймаут shell команды в api tools (сек).",
                validator=loader.validators.Integer(minimum=1, maximum=600),
            ),
            loader.ConfigValue(
                "api_tools_output_chars",
                12000,
                "макс. символов вывода api tools.",
                validator=loader.validators.Integer(minimum=1000, maximum=80000),
            ),
        )
        self.prompt_presets = []
        self.conversations = {}
        self.last_requests = {}
        self.memory_disabled_chats = set()
        self.pager_cache = {}
        self.key_model_map = {}
        self.provider_models = {}
        self.key_cooldowns = {}
        self.api_keys = []
        self._bridge_logs = {}
        self._wmodel_cache = {}
        self._cancel_flags = {}
        self._active_tasks = {}
        self._playwright = None
        self._web_browser = None
        self._web_browser_lock = asyncio.Lock()
        self._timezone_cache = None
        self._markdown_parser = None

    async def client_ready(self, client, db):
        if _witty_topic_handler not in logger.handlers:
            logger.addHandler(_witty_topic_handler)
        self.client = client
        self.db = db
        if self.config.get("provider") not in self.PROVIDER_SPECS:
            self.config["provider"] = "deepai"
        self.me = await client.get_me()
        self.api_keys = []
        self.provider_models = self.db.get(
            self.strings["name"], DB_PROVIDER_MODELS_KEY, {}
        )
        if not isinstance(self.provider_models, dict):
            self.provider_models = {}
        self.memory_disabled_chats = set(
            self.db.get(self.strings["name"], DB_MEMORY_DISABLED_KEY, [])
        )
        if not _check_module("google.genai"):
            logger.error(
                "witty: 'google-genai' library missing! pip install google-genai"
            )
            return
        self.conversations = self._load_history_from_db(DB_HISTORY_KEY)
        self.prompt_presets = self.db.get(self.strings["name"], DB_PRESETS_KEY, [])
        if isinstance(self.prompt_presets, dict):
            self.prompt_presets = [
                {"name": k, "content": v} for k, v in self.prompt_presets.items()
            ]
        self.pager_cache = self.db.get(self.strings["name"], DB_PAGER_CACHE_KEY, {})
        if not isinstance(self.pager_cache, dict):
            self.pager_cache = {}
        elif len(self.pager_cache) > MAX_PAGER_SESSIONS:
            self.pager_cache = dict(
                list(self.pager_cache.items())[-MAX_PAGER_SESSIONS:]
            )
            self.db.set(self.strings["name"], DB_PAGER_CACHE_KEY, self.pager_cache)
        global _witty_log_client, _witty_log_channel, _witty_log_topic_id
        try:
            asset_channel = self._db.get("heroku.forums", "channel_id", 0)
            if asset_channel:
                notif_topic = await utils.asset_forum_topic(
                    self._client,
                    self._db,
                    asset_channel,
                    "witty logs",
                    description="witty module warnings & errors.",
                    icon_emoji_id=5325547803936572038,
                )
                _witty_log_client = self._client
                _witty_log_channel = asset_channel
                _witty_log_topic_id = notif_topic.id
        except Exception:
            pass

    async def on_unload(self):
        tasks = {
            task
            for active in self._active_tasks.values()
            for task in active.values()
            if task and not task.done()
        }
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._active_tasks.clear()
        await self._stop_web_browser()
        logger.removeHandler(_witty_topic_handler)
        global _witty_log_client, _witty_log_channel, _witty_log_topic_id
        _witty_log_client = None
        _witty_log_channel = None
        _witty_log_topic_id = None

    def _normalize_provider_name(self, provider: str = None) -> str:
        return str(provider or self.config["provider"] or "deepai").strip().lower()

    @staticmethod
    def _bounded_cache_set(cache: dict, key, value, limit: int):
        cache.pop(key, None)
        cache[key] = value
        while len(cache) > limit:
            cache.pop(next(iter(cache)))

    def _get_timezone(self):
        name = str(self.config.get("timezone") or "UTC")
        if self._timezone_cache and self._timezone_cache[0] == name:
            return self._timezone_cache[1]
        try:
            timezone = pytz.timezone(name)
        except pytz.UnknownTimeZoneError:
            timezone = pytz.utc
        self._timezone_cache = (name, timezone)
        return timezone

    @staticmethod
    def _clean_response_text(text: str) -> str:
        result = str(text or "").strip()
        for pattern in _RESPONSE_PREFIX_PATTERNS:
            result = pattern.sub("", result)
        return result.strip()

    def _provider_spec(self, provider: str = None) -> dict:
        return self.PROVIDER_SPECS.get(
            self._normalize_provider_name(provider), self.PROVIDER_SPECS["deepai"]
        )

    def _provider_label(self, provider: str = None) -> str:
        return self._provider_spec(provider).get("label", "witty")

    def _provider_default_model(self, provider: str = None) -> str:
        return self._provider_spec(provider).get(
            "default_model", "gpt-4o-mini"
        )

    def _save_provider_models(self):
        self.db.set(self.strings["name"], DB_PROVIDER_MODELS_KEY, self.provider_models)

    def _provider_model_entry(self, provider: str = None) -> dict:
        provider = self._normalize_provider_name(provider)
        entry = self.provider_models.get(provider, "")
        if isinstance(entry, dict):
            return {"model": str(entry.get("model") or "").strip()}
        value = str(entry or "").strip()
        return {"model": value}

    def _remember_provider_model(self, provider: str = None, model_name: str = None):
        provider = self._normalize_provider_name(provider)
        if provider not in self.PROVIDER_SPECS:
            return
        model_name = str(model_name or self.config.get("model_name") or "").strip()
        if not model_name:
            return
        if self._provider_model_entry(provider).get("model") == model_name:
            return
        self.provider_models[provider] = {"model": model_name}
        self._save_provider_models()

    def _restore_provider_model(self, provider: str) -> str:
        provider = self._normalize_provider_name(provider)
        entry = self._provider_model_entry(provider)
        saved = entry.get("model")
        if saved:
            self.config["model_name"] = saved
            return saved
        default = self._provider_default_model(provider)
        self.config["model_name"] = default
        return default

    def _provider_curated_models(self, provider: str = None) -> list:
        models = self._provider_spec(provider).get("fallback_models", ()) or ()
        return list(
            dict.fromkeys(str(model).strip() for model in models if str(model).strip())
        )

    def _model_matches_provider(self, model_name: str, provider: str) -> bool:
        model = str(model_name or "").strip().lower()
        provider = self._normalize_provider_name(provider)
        if not model:
            return True
        if provider == "deepai":
            return model in DEEPAI_MODELS
        return False

    def _resolve_effective_model(
        self,
        provider: str,
        configured_model: str = None,
    ) -> str:
        provider = self._normalize_provider_name(provider)
        configured = str(
            configured_model or self.config.get("model_name") or ""
        ).strip()
        if provider == "opencode" and configured.lower().startswith("opencode/"):
            configured = configured.split("/", 1)[1]
        default = self._provider_default_model(provider)
        if configured and not self._model_matches_provider(configured, provider):
            configured = ""
        return configured or default

    def _extract_request_text_for_display(
        self, parts: list, fallback: str = None
    ) -> str:
        if fallback:
            return fallback
        chunks = []
        for part in parts or []:
            text = getattr(part, "text", None)
            if text:
                chunks.append(str(text))
        return "\n".join(chunks).strip() or "[медиа-запрос]"

    def _model_info_line(
        self,
        provider: str,
        model: str,
        elapsed: float = 0.0,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> str:
        parts = [
            f"<code>{utils.escape_html(str(model))}</code>"
        ]
        if self.config.get("show_time", True):
            parts.append(f"<b>duration:</b> <code>{round(float(elapsed or 0), 1)}s</code>")
        if self.config.get("show_tokens", True) and (tokens_in or tokens_out):
            parts.append(f"<b>in-t:</b> <code>{int(tokens_in or 0)}</code>  ·  <b>out-t:</b> <code>{int(tokens_out or 0)}</code>")
        return "  ·  ".join(parts)

    def _extract_retry_delay_seconds(self, text: str, default: int = 3600) -> int:
        raw = str(text or "")
        match = re.search(
            r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+)s", raw, flags=re.IGNORECASE
        )
        if match:
            return max(60, min(int(match.group(1)), 86400))
        match = re.search(r"retry after\s+(\d+)", raw, flags=re.IGNORECASE)
        if match:
            return max(60, min(int(match.group(1)), 86400))
        return default

    def _set_key_cooldown(self, key: str, seconds: int):
        if key:
            self.key_cooldowns[str(key)] = time.time() + max(60, int(seconds or 3600))

    def _get_openrouter_keys(self) -> list:
        raw = str(self.config.get("openrouter_keys") or "")
        return [key.strip() for key in raw.split(",") if key.strip()]

    def _get_openai_keys(self) -> list:
        raw = str(self.config.get("openai_keys") or "")
        return [key.strip() for key in raw.split(",") if key.strip()]

    def _get_claude_keys(self) -> list:
        raw = str(self.config.get("claude_keys") or "")
        return [key.strip() for key in raw.split(",") if key.strip()]

    def _get_nvidia_keys(self) -> list:
        raw = str(self.config.get("nvidia_keys") or "")
        return [key.strip() for key in raw.split(",") if key.strip()]

    def _get_deepseek_keys(self) -> list:
        raw = str(self.config.get("deepseek_keys") or "")
        return [key.strip() for key in raw.split(",") if key.strip()]

    def _get_custom_keys(self) -> list:
        raw = str(self.config.get("custom_keys") or "")
        return [key.strip() for key in raw.split(",") if key.strip()]

    def _provider_api_keys(self, provider: str = None) -> list:
        return []

    def _provider_has_key(self, provider: str = None) -> bool:
        provider = self._normalize_provider_name(provider)
        if not self._provider_spec(provider).get("requires_api_key", True):
            return True
        return False

    def _provider_keys_config_name(self, provider: str) -> str:
        return None

    async def _prepare_parts(self, message: Message, custom_text: str = None):
        final_parts, warnings = [], []
        prompt_text_chunks = []
        user_args = (
            custom_text if custom_text is not None else utils.get_args_raw(message)
        )
        chat_id = utils.get_chat_id(message)
        try:
            chat = await message.get_chat()
            chat_title = getattr(
                chat, "title", getattr(chat, "first_name", "личные сообщения")
            )
            if hasattr(chat, "is_private"):
                is_group = not bool(chat.is_private)
            elif hasattr(chat, "megagroup"):
                is_group = True
            else:
                is_group = False
        except Exception:
            chat_title = "неизвестный чат"
            is_group = False
        reply = await message.get_reply_message()
        meta_parts = [f"chat_id={chat_id}", f"chat_title='{chat_title}'"]
        meta_parts.append(f"is_group={str(is_group).lower()}")
        if reply:
            meta_parts.append(f"reply_message_id={reply.id}")
            if getattr(reply, "sender_id", None):
                meta_parts.append(f"reply_sender_id={reply.sender_id}")
        prompt_text_chunks.append(f"[Chat metadata: {','.join(meta_parts)}]")
        if reply and getattr(reply, "text", None):
            try:
                reply_sender = await reply.get_sender()
                reply_author_name = (
                    get_display_name(reply_sender) if reply_sender else "unknown"
                )
                prompt_text_chunks.append(f"{reply_author_name}: {reply.text}")
            except Exception:
                prompt_text_chunks.append(f"ответ на: {reply.text}")
        try:
            current_sender = await message.get_sender()
            current_user_name = (
                get_display_name(current_sender) if current_sender else "user"
            )
            prompt_text_chunks.append(f"{current_user_name}: {user_args or''}")
        except Exception:
            prompt_text_chunks.append(f"запрос: {user_args or''}")
        media_source = message if message.media or message.sticker else reply
        has_media = bool(media_source and (media_source.media or media_source.sticker))
        if has_media:
            if (
                media_source.sticker
                and hasattr(media_source.sticker, "mime_type")
                and media_source.sticker.mime_type == "application/x-tgsticker"
            ):
                alt_text = next(
                    (
                        attr.alt
                        for attr in media_source.sticker.attributes
                        if isinstance(attr, DocumentAttributeSticker)
                    ),
                    "?",
                )
                prompt_text_chunks.append(f"[анимированный стикер: {alt_text}]")
            else:
                media, mime_type, filename = (
                    media_source.media,
                    "application/octet-stream",
                    "file",
                )
                if media_source.photo:
                    mime_type = "image/jpeg"
                elif hasattr(media_source, "document") and media_source.document:
                    mime_type = getattr(media_source.document, "mime_type", mime_type)
                    doc_attr = next(
                        (
                            attr
                            for attr in media_source.document.attributes
                            if isinstance(attr, DocumentAttributeFilename)
                        ),
                        None,
                    )
                    if doc_attr:
                        filename = doc_attr.file_name

                async def get_bytes(m):
                    bio = io.BytesIO()
                    await self.client.download_media(m, bio)
                    return bio.getvalue()

                if mime_type.startswith("image/"):
                    try:
                        data = await get_bytes(media)
                        final_parts.append(
                            _google_types().Part(
                                inline_data=_google_types().Blob(mime_type=mime_type, data=data)
                            )
                        )
                    except Exception as e:
                        warnings.append(
                            f"ошибка обработки изображения '{filename}': {e}"
                        )
                elif mime_type in self.TEXT_MIME_TYPES or filename.split(".")[-1] in (
                    "txt",
                    "py",
                    "js",
                    "json",
                    "md",
                    "html",
                    "css",
                    "sh",
                ):
                    try:
                        data = await get_bytes(media)
                        file_content = data.decode("utf-8")
                        prompt_text_chunks.insert(
                            0,
                            f"[содержимое файла '{filename}']:\n```\n{file_content}\n```",
                        )
                    except Exception as e:
                        warnings.append(f"ошибка чтения файла '{filename}': {e}")
                elif mime_type.startswith("audio/"):
                    input_path, output_path = None, None
                    try:
                        with tempfile.NamedTemporaryFile(
                            suffix=f".{filename.split('.')[-1]}", delete=False
                        ) as temp_in:
                            input_path = temp_in.name
                        await self.client.download_media(media, input_path)
                        if os.path.getsize(input_path) > MAX_FFMPEG_SIZE:
                            warnings.append(f"аудиофайл '{filename}' слишком большой.")
                            raise StopIteration
                        with tempfile.NamedTemporaryFile(
                            suffix=".mp3", delete=False
                        ) as temp_out:
                            output_path = temp_out.name
                        ffmpeg_cmd = [
                            "ffmpeg",
                            "-y",
                            "-i",
                            input_path,
                            "-c:a",
                            "libmp3lame",
                            "-q:a",
                            "2",
                            output_path,
                        ]
                        process_ffmpeg = await asyncio.create_subprocess_exec(
                            *ffmpeg_cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        await process_ffmpeg.communicate()
                        if process_ffmpeg.returncode != 0:
                            raise Exception("ffmpeg error")
                        with open(output_path, "rb") as f:
                            final_parts.append(
                                _google_types().Part(
                                    inline_data=_google_types().Blob(
                                        mime_type="audio/mpeg", data=f.read()
                                    )
                                )
                            )
                    except StopIteration:
                        pass
                    except Exception as e:
                        warnings.append(f"ошибка обработки аудио: {e}")
                    finally:
                        if input_path and os.path.exists(input_path):
                            with contextlib.suppress(OSError):
                                os.remove(input_path)
                        if output_path and os.path.exists(output_path):
                            with contextlib.suppress(OSError):
                                os.remove(output_path)
                elif mime_type.startswith("video/"):
                    input_path, output_path = None, None
                    try:
                        with tempfile.NamedTemporaryFile(
                            suffix=f".{filename.split('.')[-1]}", delete=False
                        ) as temp_in:
                            input_path = temp_in.name
                        await self.client.download_media(media, input_path)
                        if os.path.getsize(input_path) > MAX_FFMPEG_SIZE:
                            warnings.append(f"медиафайл '{filename}' слишком большой.")
                            raise StopIteration
                        ffprobe_cmd = [
                            "ffprobe",
                            "-v",
                            "error",
                            "-select_streams",
                            "a:0",
                            "-show_entries",
                            "stream=codec_type",
                            "-of",
                            "default=noprint_wrappers=1:nokey=1",
                            input_path,
                        ]
                        process_probe = await asyncio.create_subprocess_exec(
                            *ffprobe_cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        stdout, _ = await process_probe.communicate()
                        has_audio = bool(stdout.strip())
                        with tempfile.NamedTemporaryFile(
                            suffix=".mp4", delete=False
                        ) as temp_out:
                            output_path = temp_out.name
                        ffmpeg_cmd = ["ffmpeg", "-y", "-i", input_path]
                        maps = ["-map", "0:v:0"]
                        if not has_audio:
                            ffmpeg_cmd.extend(
                                [
                                    "-f",
                                    "lavfi",
                                    "-i",
                                    "anullsrc=channel_layout=stereo:sample_rate=44100",
                                ]
                            )
                            maps.extend(["-map", "1:a:0"])
                        else:
                            maps.extend(["-map", "0:a:0?"])
                        ffmpeg_cmd.extend(
                            [
                                *maps,
                                "-vf",
                                "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                                "-c:v",
                                "libx264",
                                "-c:a",
                                "aac",
                                "-pix_fmt",
                                "yuv420p",
                                "-movflags",
                                "+faststart",
                                "-shortest",
                                output_path,
                            ]
                        )
                        process_ffmpeg = await asyncio.create_subprocess_exec(
                            *ffmpeg_cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        _, stderr = await process_ffmpeg.communicate()
                        if process_ffmpeg.returncode != 0:
                            stderr_str = stderr.decode()
                            warnings.append(
                                f"<b>ошибка ffmpeg:</b>\nне удалось конвертировать '{filename}'. детали:\n<code>{utils.escape_html(stderr_str)}</code>"
                            )
                            raise StopIteration
                        with open(output_path, "rb") as f:
                            final_parts.append(
                                _google_types().Part(
                                    inline_data=_google_types().Blob(
                                        mime_type="video/mp4", data=f.read()
                                    )
                                )
                            )
                    except StopIteration:
                        pass
                    except Exception as e:
                        warnings.append(f"ошибка обработки видео: {e}")
                    finally:
                        if input_path and os.path.exists(input_path):
                            with contextlib.suppress(OSError):
                                os.remove(input_path)
                        if output_path and os.path.exists(output_path):
                            with contextlib.suppress(OSError):
                                os.remove(output_path)

        if (
            not user_args
            and has_media
            and not final_parts
            and not any("[содержимое файла" in chunk for chunk in prompt_text_chunks)
        ):
            prompt_text_chunks.append(self.strings["media_reply_placeholder"])
        full_prompt_text = "\n".join(
            chunk for chunk in prompt_text_chunks if chunk and chunk.strip()
        ).strip()
        if full_prompt_text:
            final_parts.insert(0, _google_types().Part(text=full_prompt_text))
        return final_parts, warnings

    async def _cancel_request_cb(self, call: InlineCall, chat_id: int):
        self._cancel_flags[chat_id] = True
        tasks = self._active_tasks.pop(chat_id, None)
        if tasks:
            for task in (tasks.get("ticker"), tasks.get("api")):
                if task and not task.done():
                    task.cancel()
        try:
            await call.edit("отменено.", reply_markup=None)
        except Exception:
            try:
                await call.delete()
            except Exception:
                pass

    @staticmethod
    def _build_progress(state):
        p = state
        phase = f'<b>{utils.escape_html(str(p.get("phase", "...")))}</b>'
        meta_parts = []
        if p.get("label"):
            meta_parts.append(f'<b>{utils.escape_html(str(p["label"]))}</b>')
        if p.get("model"):
            meta_parts.append(f'<code>{utils.escape_html(str(p["model"]))}</code>')
        meta_parts.append(f"<code>{p.get('elapsed', 0)}</code>s")
        ti = p.get("tokens_in", 0)
        to_ = p.get("tokens_out", 0)
        if ti or to_:
            meta_parts.append(f"<b>in-t:</b> <code>{ti}</code>  ·  <b>out-t:</b> <code>{to_}</code>")
        elif p.get("tokens"):
            meta_parts.append(f"<b>tok:</b> <code>{p['tokens']}</code>")
        meta = "  ·  ".join(meta_parts)
        log = p.get("log", [])
        out = [f"<blockquote expandable>{phase}</blockquote>"]
        out.append(f"<blockquote expandable>{meta}</blockquote>")
        if log:
            out.append(
                f"<blockquote expandable>{utils.escape_html(chr(10).join(log[-8:]))}</blockquote>"
            )
        return "\n".join(out)

    async def _edit_progress(self, entity, text, reply_markup=None):
        if entity is None:
            return entity
        try:
            await entity.edit(text, reply_markup=reply_markup)
        except Exception as e:
            logger.debug("witty: failed to edit progress message: %s", e)
        return entity

    async def _progress_ticker(self, entity, start_time, state, reply_markup=None):
        while True:
            await asyncio.sleep(3)
            state["elapsed"] = int(time.time() - start_time)
            if entity[0] is None:
                continue
            try:
                await entity[0].edit(
                    self._build_progress(state),
                    reply_markup=reply_markup,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                pass

    async def _send_to_gemini(
        self,
        message,
        parts: list,
        regeneration: bool = False,
        call: InlineCall = None,
        status_msg=None,
        chat_id_override: int = None,
        use_url_context: bool = False,
        display_prompt: str = None,
        attempt: int = 1,
        is_retry: bool = False,
    ):
        msg_obj = None
        if regeneration or is_retry:
            chat_id = chat_id_override
            base_message_id = message
            try:
                msg_obj = await self.client.get_messages(chat_id, ids=base_message_id)
            except Exception:
                msg_obj = None
        else:
            chat_id = utils.get_chat_id(message)
            base_message_id = message.id
            msg_obj = message
        provider = self._normalize_provider_name()
        is_global = self.config["global_memory"]
        history_key = "global_context" if is_global else str(chat_id)
        target_model = self._resolve_effective_model(provider, self.config["model_name"])
        label = self._provider_label(provider)
        progress_state = {
            "phase": "thinking...",
            "model": target_model,
            "label": "",
            "elapsed": 0,
            "tokens": 0,
            "log": [],
            "prompt": display_prompt or "",
        }
        progress_entity = [status_msg]
        cancel_buttons = [
            [
                {
                    "text": "отмена",
                    "callback": self._cancel_request_cb,
                    "args": (chat_id,),
                    "style": "danger",
                }
            ]
        ]

        async def _log(msg: str):
            progress_state["log"].append(msg)

        async def _cancelled():
            return self._cancel_flags.get(chat_id, False)

        if True:
            if not self._provider_has_key(provider):
                if status_msg:
                    await utils.answer(status_msg, self.strings["no_api_key"])
                return ""
            if regeneration or is_retry:
                current_turn_parts, request_text_for_display = self.last_requests.get(
                    f"{chat_id}:{base_message_id}", (parts, "[регенерация]")
                )
            else:
                current_turn_parts = parts
                request_text_for_display = self._extract_request_text_for_display(
                    parts, display_prompt
                )
                self._bounded_cache_set(
                    self.last_requests,
                    f"{chat_id}:{base_message_id}",
                    (current_turn_parts, request_text_for_display),
                    MAX_LAST_REQUESTS,
                )
            _ticker_task = None
            try:
                target_model = self._resolve_effective_model(
                    provider,
                    self.config["model_name"],
                )
                sys_instruct = self._effective_system_prompt()
                raw_hist = self._get_structured_history(history_key)
                if regeneration and raw_hist:
                    raw_hist = raw_hist[:-2]
                openai_messages = self._convert_google_history_to_openai(
                    raw_hist, sys_instruct
                )
                content_list = []
                media_notes = []
                for p in current_turn_parts:
                    if hasattr(p, "text") and p.text:
                        content_list.append({"type": "text", "text": p.text})
                    elif hasattr(p, "inline_data") and p.inline_data:
                        mime = p.inline_data.mime_type
                        data = p.inline_data.data
                        if mime.startswith("image/"):
                            b64_img = base64.b64encode(data).decode("utf-8")
                            content_list.append(
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime};base64,{b64_img}"
                                    },
                                }
                            )
                        elif mime.startswith("audio/"):
                            media_notes.append("[аудиофайл]")
                        elif mime.startswith("video/"):
                            media_notes.append("[видеофайл]")
                        else:
                            media_notes.append("[файл]")
                if media_notes:
                    note = "контекст медиа для api: " + ", ".join(media_notes)
                    if (
                        content_list
                        and isinstance(content_list, list)
                        and content_list[0].get("type") == "text"
                    ):
                        content_list[0]["text"] = (
                            note + "\n\n" + content_list[0]["text"]
                        )
                    else:
                        content_list.insert(0, {"type": "text", "text": note})
                if not content_list:
                    content_list = request_text_for_display
                openai_messages.append({"role": "user", "content": content_list})
                if await _cancelled():
                    await _log("Cancelled")
                    return ""
                _t_start = time.time()
                progress_state["phase"] = "generating..."
                _ticker_task = asyncio.create_task(
                    self._progress_ticker(
                        progress_entity,
                        _t_start,
                        progress_state,
                        reply_markup=cancel_buttons,
                    )
                )

                async def _api_call():
                    return await self._send_to_deepai_api(
                        target_model,
                        openai_messages,
                        self.config["temperature"],
                    )

                _api_task = asyncio.create_task(_api_call())
                self._active_tasks[chat_id] = {"ticker": _ticker_task, "api": _api_task}
                _api_succeeded = False
                try:
                    result_text, usage = await _api_task
                    _api_succeeded = True
                except asyncio.CancelledError:
                    raise
                finally:
                    self._active_tasks.pop(chat_id, None)
                    if not _api_succeeded and _ticker_task and not _ticker_task.done():
                        _ticker_task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await _ticker_task
                if await _cancelled():
                    await _log("Cancelled")
                    if _ticker_task and not _ticker_task.done():
                        _ticker_task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await _ticker_task
                    return ""
                if isinstance(result_text, str):
                    for _spass in range(3):
                        _sm = re.search(
                            r"\[SEARCH:\s*([^\]]+)\]", result_text, re.IGNORECASE
                        )
                        if not _sm:
                            break
                        _sq = _sm.group(1).strip() or request_text_for_display
                        await _log(f"Search: {_sq[:60]}...")
                        try:
                            _sr = await self._web_search(
                                _sq, self.config.get("websearch_max_results", 5)
                            )
                            if not _sr:
                                break
                            progress_state["phase"] = (
                                f"{len(_sr)} results -> generating..."
                            )

                            def _fmt_sr(r):
                                ln = f"- {r.get('title','')}: {r.get('link','')}\n{r.get('snippet','')}"
                                if r.get("content"):
                                    ln += f"\nPage content: {r['content'][:1500]}"
                                return ln

                            _snote = "Web search results:\n" + "\n".join(
                                _fmt_sr(r) for r in _sr
                            )
                            openai_messages.append(
                                {"role": "assistant", "content": result_text}
                            )
                            openai_messages.append(
                                {
                                    "role": "user",
                                    "content": _snote
                                    + "\n\nUsing the above search results, answer the original question.",
                                }
                            )
                            await _log("processing results...")
                            result_text, _u2 = await _api_call()
                            usage["prompt_tokens"] = usage.get(
                                "prompt_tokens", 0
                            ) + int(
                                _u2.get("prompt_tokens")
                                or _u2.get("input_tokens")
                                or 0
                            )
                            usage["completion_tokens"] = usage.get(
                                "completion_tokens", 0
                            ) + int(
                                _u2.get("completion_tokens")
                                or _u2.get("output_tokens")
                                or 0
                            )
                        except Exception as _se:
                            logger.warning(
                                "witty: web search pass failed: %s", _se
                            )
                            break
                _elapsed = round(time.time() - _t_start, 1)
                _tokens_in = int(
                    usage.get("prompt_tokens") or usage.get("input_tokens") or 0
                )
                _tokens_out = int(
                    usage.get("completion_tokens") or usage.get("output_tokens") or 0
                )
                if not (_tokens_in or _tokens_out) and usage.get("total_tokens"):
                    _tokens_out = int(usage.get("total_tokens") or 0)
                progress_state["elapsed"] = _elapsed
                progress_state["tokens_in"] = _tokens_in
                progress_state["tokens_out"] = _tokens_out
                result_text = self._clean_response_text(result_text)
                action_summary = ""
                original_parts = list(current_turn_parts)
                original_result = result_text
                actions = []
                reply_obj = None
                if self._api_tools_enabled() and self._extract_api_tool_action(
                    result_text
                ):
                    progress_state["phase"] = "executing tools..."
                    await _log("running API tools agent loop...")
                    loop_result = await self._run_api_tools_agent_loop_openai(
                        provider=provider,
                        target_model=target_model,
                        base_messages=openai_messages,
                        temperature=self.config["temperature"],
                        progress_state=progress_state,
                    )
                    result_text = loop_result.get("text") or result_text
                    if loop_result.get("agent_log"):
                        for log_line in loop_result["agent_log"]:
                            await _log(log_line)
                if self.config.get("tg_bridge_enabled"):
                    actions = self._extract_json_actions(result_text)
                    if actions:
                        result_text = self._strip_json(result_text)
                        try:
                            reply_obj = (
                                await msg_obj.get_reply_message()
                                if isinstance(msg_obj, Message)
                                else None
                            )
                        except Exception:
                            reply_obj = None
                action_results = await self._execute_json_actions(
                    actions, msg_obj, reply_obj
                )
                if action_results:
                    action_summary = (
                        "\n".join([r for r in action_results if r != "##STOP##"])
                        or None
                    )
                    progress_state["phase"] = f"{len(action_results)} action(s) done"
                    await _log(f"{len(action_results)} action(s) done")
                    bridge_key = f"{chat_id}:{base_message_id}"
                    if action_summary:
                        self._bounded_cache_set(
                            self._bridge_logs,
                            bridge_key,
                            {"log": action_summary},
                            MAX_BRIDGE_LOGS,
                        )
                    has_stop = any("##STOP##" in r for r in action_results)
                    if not has_stop:
                        observation = "Tool result:\n" + "\n".join(action_results)
                        history = self._get_structured_history(history_key)
                        history.append(
                            {
                                "role": "user",
                                "type": "text",
                                "content": observation,
                                "date": int(time.time()),
                                "user_id": None,
                                "user_name": "system",
                                "message_id": 0,
                            }
                        )
                        self._save_history_sync()
                        await _log("processing observation...")
                        _t2 = time.time()
                        openai_messages = self._convert_google_history_to_openai(
                            self._get_structured_history(history_key),
                            self._effective_system_prompt(),
                        )
                        result_text, usage = await _api_call()

                        _elapsed2 = round(time.time() - _t2, 1)
                        _tokens_in += int(
                            usage.get("prompt_tokens") or usage.get("input_tokens") or 0
                        )
                        _tokens_out += int(
                            usage.get("completion_tokens")
                            or usage.get("output_tokens")
                            or 0
                        )
                        _elapsed += _elapsed2
                        await _log(f"+{_elapsed2}s")
                        result_text = result_text.strip()
                        actions2 = self._extract_json_actions(result_text)
                        if actions2:
                            result_text = self._strip_json(result_text)
                            try:
                                reply_obj = (
                                    await msg_obj.get_reply_message()
                                    if isinstance(msg_obj, Message)
                                    else None
                                )
                            except Exception:
                                reply_obj = None
                            action_results2 = await self._execute_json_actions(
                                actions2, msg_obj, reply_obj
                            )
                            if action_results2:
                                result_text += "\n\n" + "\n".join(action_results2)
                                self._bounded_cache_set(
                                    self._bridge_logs,
                                    bridge_key,
                                    {
                                        "log": (action_summary or "")
                                        + "\n"
                                        + "\n".join(action_results2)
                                    },
                                    MAX_BRIDGE_LOGS,
                                )
                result_text = result_text.strip()
                if self._is_memory_enabled(str(chat_id)):
                    self._update_history(
                        history_key,
                        original_parts,
                        original_result,
                        regeneration,
                        msg_obj,
                    )
                hist_len = len(self._get_structured_history(history_key)) // 2
                max_hist = self.config["max_history_length"]
                if is_global:
                    mem_indicator = self.strings["memory_status_global"].format(
                        hist_len
                    )
                elif max_hist <= 0:
                    mem_indicator = self.strings["memory_status_unlimited"].format(
                        hist_len
                    )
                else:
                    mem_indicator = self.strings["memory_status"].format(
                        hist_len, max_hist
                    )
                model_info = self._model_info_line(
                    provider, target_model, _elapsed, _tokens_in, _tokens_out
                )
                if attempt > 1:
                    model_info += f"  ·  <b>попытка</b> <code>{attempt}</code>"
                response_html = self._markdown_to_html(result_text)
                q_esc = utils.escape_html(request_text_for_display[:200])
                text_to_send = (
                    f"<b>{mem_indicator}</b>\n{model_info}\n\n"
                    f"{self._rich_details('Запрос', q_esc)}\n\n"
                    f"{self._rich_details('Ответ', response_html)}"
                )
                if action_summary:
                    bridge_key = f"{chat_id}:{base_message_id}"
                    self._bounded_cache_set(
                        self._bridge_logs,
                        bridge_key,
                        {"response": text_to_send, "log": action_summary},
                        MAX_BRIDGE_LOGS,
                    )
                buttons = (
                    self._get_inline_buttons(chat_id, base_message_id)
                    if self.config["interactive_buttons"]
                    else None
                )
                if _ticker_task and not _ticker_task.done():
                    _ticker_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await _ticker_task
                if len(text_to_send) > 4096:
                    try:
                        if status_msg:
                            await status_msg.delete()
                    except Exception:
                        pass
                    file = io.BytesIO(result_text.encode("utf-8"))
                    file.name = "witty_response.txt"
                    if call:
                        await self.client.send_file(
                            call.chat_id,
                            file,
                            caption="response too long",
                            reply_to=call.message_id,
                        )
                    else:
                        await self.client.send_file(
                            chat_id,
                            file,
                            caption="response too long",
                            reply_to=base_message_id,
                        )
                else:
                    try:
                        if status_msg:
                            await status_msg.delete()
                    except Exception:
                        pass
                    if call:
                        await call.edit(text_to_send, reply_markup=buttons)
                    else:
                        await utils.answer(msg_obj, text_to_send, reply_markup=buttons)
                return ""
            except asyncio.CancelledError:
                if _ticker_task and not _ticker_task.done():
                    _ticker_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await _ticker_task
                return ""
            except Exception as e:
                if _ticker_task and not _ticker_task.done():
                    _ticker_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await _ticker_task
                error_text = self._handle_error(e)
                error_buttons = None
                if base_message_id:
                    btn_action = "regen_att" if regeneration else "retry"
                    is_regen_flag = "1" if regeneration else "0"
                    error_buttons = [
                        [
                            {
                                "text": f"повторить ({attempt + 1})",
                                "data": f"witty:{btn_action}:{chat_id}:{base_message_id}:{attempt + 1}",
                            },
                            {
                                "text": "запрос",
                                "data": f"witty:shreq:{is_regen_flag}:{chat_id}:{base_message_id}:{attempt + 1}",
                            },
                        ]
                    ]
                if call:
                    await call.edit(error_text, reply_markup=error_buttons)
                elif status_msg:
                    await utils.answer(
                        status_msg, error_text, reply_markup=error_buttons
                    )
                return None
    @loader.command()
    async def w(self, message: Message):
        """[текст или reply] - спросить у witty. может анализировать ссылки."""
        clean_args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        use_url_context = False
        text_to_check = clean_args
        if reply and getattr(reply, "text", None):
            text_to_check += reply.text
        if re.search(r"https?://\S+", text_to_check):
            use_url_context = True
        provider = self._normalize_provider_name()
        model = self._resolve_effective_model(provider, self.config["model_name"])
        chat_id = utils.get_chat_id(message)
        self._cancel_flags.pop(chat_id, None)
        cancel_btns = [
            [
                {
                    "text": "отмена",
                    "callback": self._cancel_request_cb,
                    "args": (chat_id,),
                    "style": "danger",
                }
            ]
        ]
        progress_state = {
            "phase": "preparing request...",
            "model": model,
            "label": "",
            "elapsed": 0,
            "tokens": 0,
            "log": [],
            "prompt": clean_args or "[медиа-запрос]",
        }
        status_msg = await self.inline.form(
            text=self._build_progress(progress_state),
            message=message,
            reply_markup=cancel_btns,
        )
        try:
            parts, warnings = await self._prepare_parts(message, custom_text=clean_args)
            if warnings:
                progress_state["log"].extend(warnings)
                await self._edit_progress(
                    status_msg,
                    self._build_progress(progress_state),
                    reply_markup=cancel_btns,
                )
            if not parts:
                if status_msg:
                    await utils.answer(status_msg, self.strings["no_prompt_or_media"])
                return
            await self._send_to_gemini(
                message=message,
                parts=parts,
                status_msg=status_msg,
                use_url_context=use_url_context,
                display_prompt=clean_args or None,
            )
        finally:
            self._cancel_flags.pop(chat_id, None)

    @loader.command()
    async def wprompt(self, message: Message):
        """<текст/-c/ответ на файл> - установить промпт."""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        if args == "-c":
            self.config["system_instruction"] = ""
            return await utils.answer(message, self.strings["wprompt_cleared"])
        new_prompt = None
        preset = self._find_preset(args)
        if preset:
            new_prompt = preset["content"]
        elif reply and reply.file:
            if reply.file.size > 1024 * 1024:
                return await utils.answer(message, self.strings["wprompt_file_too_big"])
            try:
                file_data = await self.client.download_file(reply.media, bytes)
                try:
                    new_prompt = file_data.decode("utf-8")
                except UnicodeDecodeError:
                    return await utils.answer(message, self.strings["wprompt_not_text"])
            except Exception as e:
                return await utils.answer(
                    message, self.strings["wprompt_file_error"].format(e)
                )
        elif args:
            new_prompt = args
        if new_prompt is not None:
            self.config["system_instruction"] = new_prompt
            return await utils.answer(
                message, self.strings["wprompt_updated"].format(len(new_prompt))
            )
        current_prompt = self.config["system_instruction"]
        if not current_prompt:
            return await utils.answer(message, self.strings["wprompt_usage"])
        if len(current_prompt) > 4000:
            file = io.BytesIO(current_prompt.encode("utf-8"))
            file.name = "system_instruction.txt"
            await utils.answer(message, self.strings["wprompt_current"], file=file)
        else:
            await utils.answer(
                message,
                f"{self.strings['wprompt_current']}\n<code>{utils.escape_html(current_prompt)}</code>",
            )

    @loader.command()
    async def wpresets(self, message: Message):
        """<save/load/del/list> - управление пресетами (профилями)."""
        args = utils.get_args_raw(message)
        if not args:
            return await utils.answer(message, self.strings["wpresets_usage"])
        match = re.match(
            r"^(\w+)(?:\s+\[(.+?)\]|\s+(\S+))?(?:\s+(.*))?$", args, re.DOTALL
        )
        if not match:
            return await utils.answer(message, self.strings["wpresets_usage"])
        action = match.group(1).lower()
        name = match.group(2) or match.group(3)
        content = match.group(4)
        if action == "list":
            if not self.prompt_presets:
                return await utils.answer(message, self.strings["wpreset_empty"])
            text = self.strings["wpreset_list_head"]
            for idx, p in enumerate(self.prompt_presets, 1):
                text += f"<b>{idx}.</b> <code>{p['name']}</code> ({len(p['content'])} симв.)\n"
            return await utils.answer(message, text)
        if action == "save":
            if not name:
                return await utils.answer(
                    message, "укажите имя: <code>.wpresets save [имя] текст</code>"
                )
            reply = await message.get_reply_message()
            if not content and reply:
                if reply.text:
                    content = reply.text
                elif reply.file:
                    try:
                        content = (
                            await self.client.download_file(reply.media, bytes)
                        ).decode("utf-8", errors="ignore")
                    except:
                        pass
            if not content:
                return await utils.answer(message, "нет текста для сохранения.")
            existing = self._find_preset(name)
            if existing:
                existing["content"] = content
            else:
                self.prompt_presets.append({"name": name, "content": content})
            self.db.set(self.strings["name"], DB_PRESETS_KEY, self.prompt_presets)
            await utils.answer(
                message,
                self.strings["wpreset_saved"].format(name, len(self.prompt_presets)),
            )
        elif action == "load":
            target = self._find_preset(name)
            if not target:
                return await utils.answer(message, self.strings["wpreset_not_found"])
            self.config["system_instruction"] = target["content"]
            await utils.answer(
                message,
                self.strings["wpreset_loaded"].format(
                    target["name"], len(target["content"])
                ),
            )
        elif action == "del":
            target = self._find_preset(name)
            if not target:
                return await utils.answer(message, self.strings["wpreset_not_found"])
            self.prompt_presets.remove(target)
            self.db.set(self.strings["name"], DB_PRESETS_KEY, self.prompt_presets)
            await utils.answer(
                message, self.strings["wpreset_deleted"].format(target["name"])
            )
        else:
            await utils.answer(message, self.strings["wpresets_usage"])

    def _find_preset(self, query):
        "ищет пресет по номеру (строка '1') или имени."
        if not query:
            return None
        if str(query).isdigit():
            idx = int(query) - 1
            if 0 <= idx < len(self.prompt_presets):
                return self.prompt_presets[idx]
        for p in self.prompt_presets:
            if p["name"].lower() == str(query).lower():
                return p
        return None

    @loader.command()
    async def wmemdel(self, message: Message):
        """[n] - удалить последние n пар сообщений из памяти."""
        try:
            n = int(utils.get_args_raw(message) or 1)
        except:
            n = 1
        cid = (
            "global_context"
            if self.config["global_memory"]
            else utils.get_chat_id(message)
        )
        hist = self._get_structured_history(cid)
        if n > 0 and len(hist) >= n * 2:
            self.conversations[str(cid)] = hist[: -n * 2]
            self._save_history_sync()
            await utils.answer(
                message, f"удалено последних <b>{n}</b> пар сообщений из памяти."
            )
        else:
            await utils.answer(message, "недостаточно истории для удаления.")

    @loader.command()
    async def wmemchats(self, message: Message):
        """- показать список чатов с активной памятью (имя и id)."""
        if not self.conversations:
            return await utils.answer(message, self.strings["no_memory_found"])
        out = [self.strings["memory_chats_title"].format(len(self.conversations))]
        shown = set()
        for cid in list(self.conversations.keys()):
            if not str(cid).lstrip("-").isdigit():
                continue
            chat_id = int(cid)
            if chat_id in shown:
                continue
            shown.add(chat_id)
            try:
                e = await self.client.get_entity(chat_id)
                name = get_display_name(e)
            except:
                name = f"unknown ({chat_id})"
            out.append(self.strings["memory_chat_line"].format(name, chat_id))
        if len(out) == 1:
            return await utils.answer(message, self.strings["no_memory_found"])
        await utils.answer(message, "\n".join(out))

    @loader.command()
    async def wmemexport(self, message: Message):
        """[<id/@юз чата>] [-s] - экспорт памяти. -s в избранное."""
        args = utils.get_args_raw(message).split()
        save_to_self = "-s" in args
        if save_to_self:
            args.remove("-s")
        source_chat_id_str = args[0] if args else None
        target_chat_id = "me" if save_to_self else message.chat_id
        if source_chat_id_str:
            try:
                entity = await self.client.get_entity(
                    int(source_chat_id_str)
                    if source_chat_id_str.lstrip("-").isdigit()
                    else source_chat_id_str
                )
                source_chat_id = entity.id
                hist = self._get_structured_history(source_chat_id)
            except Exception:
                await utils.answer(
                    message,
                    self.strings["wme_chat_not_found"].format(
                        utils.escape_html(source_chat_id_str)
                    ),
                )
                return
        else:
            source_chat_id = utils.get_chat_id(message)
            hist = self._get_structured_history(source_chat_id)
        if not hist:
            await utils.answer(message, "история для экспорта пуста.")
            return
        user_ids = {
            e.get("user_id")
            for e in hist
            if e.get("role") == "user" and e.get("user_id")
        }
        user_names = {None: None}
        for uid in user_ids:
            if not uid:
                continue
            try:
                entity = await self.client.get_entity(uid)
                user_names[uid] = get_display_name(entity)
            except Exception:
                user_names[uid] = f"deleted account ({uid})"

        def make_serializable(entry):
            entry = dict(entry)
            user_id = entry.get("user_id")
            if user_id:
                entry["user_name"] = user_names.get(user_id)
            if hasattr(user_id, "user_id"):
                entry["user_id"] = user_id.user_id
            elif isinstance(user_id, (int, str)):
                entry["user_id"] = user_id
            elif user_id is not None:
                entry["user_id"] = str(user_id)
            else:
                entry["user_id"] = None
            if "message_id" in entry and entry["message_id"] is not None:
                try:
                    entry["message_id"] = int(entry["message_id"])
                except:
                    entry["message_id"] = None
            return entry

        serializable_hist = [make_serializable(e) for e in hist]
        data = json.dumps(serializable_hist, ensure_ascii=False, indent=2)
        file = io.BytesIO(data.encode("utf-8"))
        file.name = f"gemini_history_{source_chat_id}.json"
        caption = "экспорт памяти witty"
        if source_chat_id != utils.get_chat_id(message):
            caption += f" из чата <code>{source_chat_id}</code>"
        await self.client.send_file(
            target_chat_id,
            file,
            caption=caption,
            reply_to=message.id if target_chat_id == message.chat_id else None,
        )
        if save_to_self:
            if target_chat_id == "me" and message.chat_id != self.me.id:
                await utils.answer(message, self.strings["wme_sent_to_saved"])
            else:
                await message.delete()

    @loader.command()
    async def wmemimport(self, message: Message):
        """- импорт истории из файла (реплай на json-файл)."""
        reply = await message.get_reply_message()
        if not reply or not reply.document:
            return await utils.answer(message, "ответьте на json-файл с памятью.")
        max_import_size = 15 * 1024 * 1024
        if getattr(reply.file, "size", 0) > max_import_size:
            return await utils.answer(
                message,
                f"файл слишком большой (>{max_import_size // (1024 * 1024)} мб).",
            )
        file = io.BytesIO()
        await self.client.download_media(reply, file)
        file.seek(0)
        if file.getbuffer().nbytes > max_import_size:
            return await utils.answer(
                message,
                f"файл слишком большой (>{max_import_size // (1024 * 1024)} мб).",
            )
        try:
            hist = json.load(file)
            if not isinstance(hist, list):
                raise ValueError("файл не содержит список истории.")
            new_hist = []
            for e in hist:
                if not isinstance(e, dict) or "role" not in e or "content" not in e:
                    raise ValueError("некорректная структура памяти.")
                entry = {
                    "role": e["role"],
                    "type": e.get("type", "text"),
                    "content": e["content"],
                    "date": e.get("date"),
                }
                if e["role"] == "user":
                    entry["user_id"] = e.get("user_id")
                    entry["message_id"] = e.get("message_id")
                new_hist.append(entry)
            chat_id = str(utils.get_chat_id(message))
            self.conversations[chat_id] = new_hist
            self._save_history_sync()
            await utils.answer(
                message, f"память успешно импортирована ({len(new_hist)//2} диалогов)."
            )
        except Exception as e:
            await utils.answer(message, f"ошибка импорта: {e}")

    @loader.command()
    async def wmemfind(self, message: Message):
        """[слово] - поиск в памяти текущего чата по ключевому слову или фразе."""
        q = utils.get_args_raw(message).lower()
        if not q:
            return await utils.answer(message, "укажите слово для поиска.")
        cid = (
            "global_context"
            if self.config["global_memory"]
            else utils.get_chat_id(message)
        )
        hist = self._get_structured_history(cid)
        found = [
            f"{e['role']}: {e.get('content','')[:200]}"
            for e in hist
            if q in str(e.get("content", "")).lower()
        ]
        if not found:
            await utils.answer(message, "ничего не найдено.")
        else:
            await utils.answer(message, "\n\n".join(found[:10]))

    @loader.command()
    async def wmemoff(self, message: Message):
        """- отключить память в этом чате."""
        self.memory_disabled_chats.add(str(utils.get_chat_id(message)))
        self.db.set(
            self.strings["name"],
            DB_MEMORY_DISABLED_KEY,
            list(self.memory_disabled_chats),
        )
        await utils.answer(message, "память в этом чате отключена.")

    @loader.command()
    async def wmemon(self, message: Message):
        """- включить память в этом чате."""
        self.memory_disabled_chats.discard(str(utils.get_chat_id(message)))
        self.db.set(
            self.strings["name"],
            DB_MEMORY_DISABLED_KEY,
            list(self.memory_disabled_chats),
        )
        await utils.answer(message, "память в этом чате включена.")

    @loader.command()
    async def wmemshow(self, message: Message):
        """- показать память чата (до 20 последних запросов)."""
        args = utils.get_args_raw(message).lower()
        cid = (
            "global_context"
            if ("global" in args or self.config["global_memory"])
            else utils.get_chat_id(message)
        )
        hist = self._get_structured_history(cid)
        if not hist:
            return await utils.answer(message, "память пуста.")
        out = []
        for e in hist[-40:]:
            role = e.get("role")
            content = utils.escape_html(str(e.get("content", ""))[:300])
            if role == "user":
                out.append(f"{content}")
            elif role == "model":
                out.append(f"<b>witty:</b> {content}")
        await utils.answer(
            message, "<blockquote expandable='true'>" + "\n".join(out) + "</blockquote>"
        )

    @loader.command()
    async def wmodel(self, message: Message):
        """[model] [-s] - узнать/сменить модель. -s - список. авто-проверка совместимости."""
        args_raw = utils.get_args_raw(message).strip()
        args = args_raw.lower()
        provider = self._normalize_provider_name()
        if args in ("-s", "--s", "s", "list"):
            status_msg = await utils.answer(message, self.strings["processing"])
            try:
                models = await self._get_provider_model_catalog(provider)
                if not models:
                    raise ValueError(self.strings["wmodel_no_models"])
                uid = uuid.uuid4().hex[:8]
                self._bounded_cache_set(
                    self._wmodel_cache,
                    uid,
                    {"models": models, "provider": provider},
                    MAX_MODEL_SESSIONS,
                )
                text, btns = self._wmodel_build_view(uid, 0, "")
                await self.inline.form(text=text, message=status_msg, reply_markup=btns)
            except Exception as e:
                await utils.answer(
                    status_msg,
                    self.strings["wmodel_list_error"].format(self._handle_error(e)),
                )
            return
        if not args_raw:
            effective = self._resolve_effective_model(provider, self.config["model_name"])
            return await utils.answer(
                message,
                f"<b>провайдер:</b> <code>{self._provider_label(provider)}</code>\n"
                f"<b>модель в конфиге:</b> <code>{utils.escape_html(str(self.config['model_name']))}</code>\n"
                f"<b>эффективная модель:</b> <code>{utils.escape_html(effective)}</code>",
            )
        self.config["model_name"] = args_raw
        self._remember_provider_model(provider, args_raw)
        warning = ""
        if not self._model_matches_provider(args_raw, provider):
            warning = (
                "\n\n<b>возможна несовместимость.</b>\n"
                f"модель <code>{utils.escape_html(args_raw)}</code> может не поддерживаться провайдером <b>{self._provider_label(provider)}</b>.\n"
                "если не работает, верните модель по умолчанию: <code>.wmodel gpt-4o-mini</code>"
            )
        await utils.answer(
            message,
            f"модель установлена: <code>{utils.escape_html(args_raw)}</code>{warning}",
        )

    @loader.command()
    async def wres(self, message: Message):
        """[global] - очистить память чата. global - всю память безоговорочно."""
        args = utils.get_args_raw(message).strip().lower()
        chat_id = utils.get_chat_id(message)
        clear_all = args == "global" or self.config["global_memory"]
        if clear_all:
            if not self.conversations:
                return await utils.answer(
                    message, self.strings["no_memory_to_fully_clear"]
                )
            count = len(self.conversations)
            self.conversations.clear()
            self._save_history_sync()
            await utils.answer(
                message, self.strings["memory_fully_cleared"].format(count)
            )
        else:
            hist_key = str(chat_id)
            if hist_key not in self.conversations:
                return await utils.answer(message, self.strings["no_memory_to_clear"])
            self._clear_history(hist_key)
            keys_to_del = [
                k for k, v in self.pager_cache.items() if v.get("chat_id") == chat_id
            ]
            for k in keys_to_del:
                del self.pager_cache[k]
            if keys_to_del:
                self.db.set(self.strings["name"], DB_PAGER_CACHE_KEY, self.pager_cache)
            await utils.answer(message, self.strings["memory_cleared"])

    @loader.callback_handler()
    async def witty_callback_handler(self, call: InlineCall):
        if not call.data.startswith("witty:"):
            return
        parts = call.data.split(":")
        action = parts[1]

        if action == "noop":
            await call.answer()
            return
        if action == "close":
            uid = parts[2]
            if uid in self.pager_cache:
                del self.pager_cache[uid]
                self.db.set(self.strings["name"], DB_PAGER_CACHE_KEY, self.pager_cache)
            try:
                await call.answer()
            except:
                pass
            try:
                chat = call.chat_id
                msg_id = call.message_id
                if chat and msg_id:
                    await self.client.delete_messages(chat, msg_id)
                else:
                    await call.delete()
            except Exception:
                try:
                    await call.edit("<b>сессия закрыта.</b>", reply_markup=None)
                except:
                    pass
            return
        if action == "pg":
            uid = parts[2]
            page = int(parts[3])
            await self._render_page(uid, page, call)
            return
        if action in ("regen", "regen_att"):
            chat_id = int(parts[2])
            msg_id = int(parts[3])
            attempt = int(parts[4]) if action == "regen_att" and len(parts) > 4 else 1
            key = f"{chat_id}:{msg_id}"
            last_request_tuple = self.last_requests.get(key)
            if not last_request_tuple:
                await call.answer(self.strings["no_last_request"], show_alert=True)
                return
            last_parts, display_prompt = last_request_tuple
            use_url_context = bool(re.search(r"https?://\S+", display_prompt or ""))
            await call.edit(
                (
                    f"<b>регенерация (попытка {attempt})...</b>"
                    if attempt > 1
                    else "<b>регенерация...</b>"
                ),
                reply_markup=None,
            )
            try:
                await self._send_to_gemini(
                    message=msg_id,
                    parts=last_parts,
                    regeneration=True,
                    call=call,
                    chat_id_override=chat_id,
                    use_url_context=use_url_context,
                    display_prompt=display_prompt,
                    attempt=attempt,
                )
            finally:
                self._cancel_flags.pop(chat_id, None)
            return
        if action == "retry":
            chat_id = int(parts[2])
            msg_id = int(parts[3])
            attempt = int(parts[4]) if len(parts) > 4 else 1
            key = f"{chat_id}:{msg_id}"
            last_request_tuple = self.last_requests.get(key)
            if not last_request_tuple:
                await call.answer(self.strings["no_last_request"], show_alert=True)
                return
            last_parts, display_prompt = last_request_tuple
            use_url_context = bool(re.search(r"https?://\S+", display_prompt or ""))
            await call.edit(
                f"<b>обработка (попытка {attempt})...</b>", reply_markup=None
            )
            try:
                await self._send_to_gemini(
                    message=msg_id,
                    parts=last_parts,
                    regeneration=False,
                    call=call,
                    chat_id_override=chat_id,
                    use_url_context=use_url_context,
                    display_prompt=display_prompt,
                    attempt=attempt,
                    is_retry=True,
                )
            finally:
                self._cancel_flags.pop(chat_id, None)
            return
        if action == "shreq":
            is_regen_flag = parts[2]
            chat_id = int(parts[3])
            msg_id = int(parts[4])
            attempt = int(parts[5]) if len(parts) > 5 else 1
            key = f"{chat_id}:{msg_id}"
            last_request_tuple = self.last_requests.get(key)
            if not last_request_tuple:
                await call.answer(self.strings["no_last_request"], show_alert=True)
                return
            _, display_prompt = last_request_tuple
            btn_action = "regen_att" if is_regen_flag == "1" else "retry"
            await call.edit(
                f"<b>ваш запрос:</b>\n<code>{utils.escape_html(display_prompt)}</code>",
                reply_markup=[
                    [
                        {
                            "text": f"повторить ({attempt})",
                            "data": f"witty:{btn_action}:{chat_id}:{msg_id}:{attempt}",
                        }
                    ]
                ],
            )
            return

    async def _render_page(self, uid, page_num, entity):
        data = self.pager_cache.get(uid)
        if not data:
            if isinstance(entity, InlineCall):
                await entity.edit(
                    "<b>сессия истекла или бот был перезагружен с потерей данных.</b>",
                    reply_markup=[[{"text": "удалить", "data": f"witty:close:{uid}"}]],
                )
            return
        chunks = data["chunks"]
        total = data["total"]
        header = data.get("header", "")
        chat_id = data.get("chat_id")
        base_msg_id = data.get("msg_id")
        raw_text_chunk = chunks[page_num]
        safe_text = self._markdown_to_html(raw_text_chunk)
        text_to_show = f"{header}{self._rich_details('Ответ', safe_text)}"
        nav_row = []
        if page_num > 0:
            nav_row.append({"text": "<", "data": f"witty:pg:{uid}:{page_num - 1}"})
        nav_row.append({"text": f"{page_num + 1}/{total}", "data": "witty:noop"})
        if page_num < total - 1:
            nav_row.append({"text": ">", "data": f"witty:pg:{uid}:{page_num + 1}"})
        extra_row = [{"text": "закрыть", "data": f"witty:close:{uid}", "style": "danger"}]
        if chat_id and base_msg_id:
            extra_row.append(
                {"text": "retry", "data": f"witty:regen:{chat_id}:{base_msg_id}"}
            )
        buttons = [nav_row, extra_row]
        if isinstance(entity, Message):
            await self.inline.form(
                text=text_to_show, message=entity, reply_markup=buttons
            )
        elif isinstance(entity, InlineCall):
            await entity.edit(text=text_to_show, reply_markup=buttons)
        elif hasattr(entity, "edit"):
            try:
                await entity.edit(text=text_to_show, reply_markup=buttons)
            except:
                pass

    def _paginate_text(self, text: str, limit: int) -> list:
        pages = []
        current_page_lines = []
        current_len = 0
        in_code_block = False
        current_code_lang = ""
        lines = text.split("\n")
        for line in lines:
            line_len = len(line) + 1
            stripped = line.strip()
            if stripped.startswith("```"):
                if in_code_block:
                    in_code_block = False
                    current_code_lang = ""
                else:
                    in_code_block = True
                    current_code_lang = stripped.replace("```", "").strip()
            if current_len + line_len > limit:
                if current_page_lines:
                    if in_code_block:
                        current_page_lines.append("```")
                    pages.append("\n".join(current_page_lines))
                    current_page_lines = []
                    current_len = 0
                    if in_code_block:
                        header = f"```{current_code_lang}"
                        current_page_lines.append(header)
                        current_len += len(header) + 1
                if line_len > limit:
                    chunks = [line[i : i + limit] for i in range(0, len(line), limit)]
                    for chunk in chunks:
                        if current_len + len(chunk) > limit:
                            pages.append("\n".join(current_page_lines))
                            current_page_lines = [chunk]
                            current_len = len(chunk)
                        else:
                            current_page_lines.append(chunk)
                            current_len += len(chunk)
                    continue
            current_page_lines.append(line)
            current_len += line_len
        if current_page_lines:
            pages.append("\n".join(current_page_lines))
        return pages

    def _get_proxy_config(self):
        p = self.config["proxy"]
        return {"http://": p, "https://": p} if p else None

    def _save_history_sync(self):
        if getattr(self, "_db_broken", False):
            return
        try:
            self.db.set(self.strings["name"], DB_HISTORY_KEY, self.conversations)
        except:
            self._db_broken = True

    def _load_history_from_db(self, key):
        d = self.db.get(self.strings["name"], key, {})
        return d if isinstance(d, dict) else {}

    def _get_structured_history(self, cid):
        if str(cid) not in self.conversations:
            self.conversations[str(cid)] = []
        return self.conversations[str(cid)]

    def _update_history(
        self,
        chat_id: int,
        user_parts: list,
        model_response: str,
        regeneration: bool = False,
        message: Message = None,
    ):
        if not self._is_memory_enabled(str(chat_id)):
            return
        history = self._get_structured_history(chat_id)
        now = int(time.time())
        user_id = self.me.id
        user_name = get_display_name(self.me)
        message_id = getattr(message, "id", None)
        if message:
            try:
                peer_id = get_peer_id(message)
                if peer_id:
                    user_id = peer_id
            except (TypeError, ValueError):
                if message.sender_id:
                    user_id = message.sender_id
            if message.sender:
                user_name = get_display_name(message.sender)
        user_text = (
            "".join([p.text for p in user_parts if hasattr(p, "text") and p.text])
            or "[ответ на медиа]"
        )
        if regeneration and history:
            for i in range(len(history) - 1, -1, -1):
                if history[i].get("role") == "model":
                    history[i].update({"content": model_response, "date": now})
                    break
        else:
            user_entry = {
                "role": "user",
                "type": "text",
                "content": user_text,
                "date": now,
                "user_id": user_id,
                "message_id": message_id,
                "user_name": user_name,
            }
            model_entry = {
                "role": "model",
                "type": "text",
                "content": model_response,
                "date": now,
                "user_id": None,
            }
            history.extend([user_entry, model_entry])
        limit = self.config["max_history_length"]
        if limit > 0 and len(history) > limit * 2:
            history = history[-(limit * 2) :]
        self.conversations[str(chat_id)] = history
        self._save_history_sync()

    def _clear_history(self, cid):
        if str(cid) in self.conversations:
            del self.conversations[str(cid)]
            self._save_history_sync()

    def _handle_error(self, e: Exception) -> str:
        logger.exception("witty execution error")
        if isinstance(e, asyncio.TimeoutError):
            return self.strings["api_timeout"]
        google_errors = _google_exceptions()
        if isinstance(e, google_errors.GoogleAPIError):
            msg = str(e)
            if "quota" in msg.lower() or "exceeded" in msg.lower():
                model_name = self.config.get("model_name", "unknown")
                model_name_match = re.search(r'key:"model"\s+value:"([^"]+)"', msg)
                if model_name_match:
                    model_name = model_name_match.group(1)
                return (
                    f"<b>превышен лимит google gemini api для модели <code>{utils.escape_html(model_name)}</code>.</b>"
                    "\n\nчаще всего это происходит на бесплатном тарифе. вы можете:\n"
                    "- подождать, пока лимит сбросится (обычно раз в сутки).\n"
                    "- проверить свой тарифный план в <a href='https://aistudio.google.com/app/billing'>google ai studio</a>.\n"
                    "- узнать больше о лимитах <a href='https://ai.google.dev/gemini-api/docs/rate-limits'>здесь</a>.\n\n"
                    f"<b>детали ошибки:</b>\n<code>{utils.escape_html(msg)}</code>"
                )
            if "500 An internal error has occurred" in msg:
                return (
                    "<b>ошибка 500 от google api.</b>\n"
                    "это значит, что формат медиа (файл или еще что то) который ты отправил, не поддерживается.\n"
                    "такое случается по такой причине:\n"
                    "- если формат файла в принципе не поддерживается gemini/гуглом.\n"
                    "- временный сбой на серверах google. попробуйте повторить запрос позже."
                )
            if (
                "User location is not supported" in msg
                or "location is not supported" in msg
            ):
                return (
                    "<b>в данном регионе gemini api не доступен.</b>\n"
                    "скачайте vpn (для пк/тел) или поставьте прокси (платный/бесплатный).\n"
                    'или воспользуйтесь инструкцией <a href="https://t.me/SenkoGuardianModules/23">вот тут</a>\n'
                    'а для тех у кого userland инструкция <a href="https://t.me/SenkoGuardianModules/35">тут</a>'
                )
            if "API key not valid" in msg:
                return self.strings["invalid_api_key"]
            if "blocked" in msg.lower():
                return self.strings["blocked_error"].format(utils.escape_html(msg))
            return self.strings["api_error"].format(utils.escape_html(msg))
        if isinstance(e, (OSError, aiohttp.ClientError, socket.timeout)):
            return "<b>сетевая ошибка:</b>\n<code>{}</code>".format(
                utils.escape_html(str(e))
            )
        msg = str(e)
        if (
            "No API_KEY or ADC found" in msg
            or "GOOGLE_API_KEY environment variable" in msg
            or "genai.configure(api_key" in msg
        ):
            return self.strings["no_api_key"]
        if "quota" in msg.lower() or "429" in msg:
            return self.strings["all_keys_exhausted"].format(len(self.api_keys))
        return self.strings["generic_error"].format(utils.escape_html(msg))

    def _markdown_to_html(self, text: str) -> str:
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL)
        text = re.sub(r"(?i)<br\s*/?>", "\n", text)

        def heading_replacer(match):
            title = match.group(2).strip()
            return f"<b>{title}</b>"

        text = re.sub(r"^(#+)\s+(.*)", heading_replacer, text, flags=re.MULTILINE)

        def list_replacer(match):
            indent = match.group(1)
            return f"{indent}-"

        text = re.sub(r"^([ \t]*)[-*+]\s+", list_replacer, text, flags=re.MULTILINE)
        if self._markdown_parser is None:
            from markdown_it import MarkdownIt

            parser = MarkdownIt("commonmark", {"html": True, "linkify": True})
            parser.enable("strikethrough")
            parser.disable("hr")
            parser.disable("heading")
            parser.disable("list")
            self._markdown_parser = parser
        html_text = self._markdown_parser.render(text)

        html_text = re.sub(
            r"<p>(<pre>[\s\S]*?</pre>)</p>", r"\1", html_text, flags=re.DOTALL
        )
        html_text = html_text.replace("<p>", "").replace("</p>", "\n")
        html_text = re.sub(r"(?i)<br\s*/?>", "\n", html_text).strip()
        return html_text

    @staticmethod
    def _rich_details(title: str, content: str) -> str:
        """Build a Telegram rich-message equivalent of a collapsed HTML details block."""
        return f"<b>{title}:</b>\n<blockquote expandable>{content}</blockquote>"

    def _get_inline_buttons(self, chat_id, base_message_id):
        btns = [
            [
                {
                    "text": self.strings["btn_clear"],
                    "callback": self._clear_callback,
                    "args": (chat_id,),
                },
                {
                    "text": self.strings["btn_regenerate"],
                    "data": f"witty:regen:{chat_id}:{base_message_id}",
                },
            ]
        ]
        bridge_key = f"{chat_id}:{base_message_id}"
        if bridge_key in self._bridge_logs:
            btns.append(
                [
                    {
                        "text": "мост",
                        "callback": self._bridge_log_cb,
                        "args": (bridge_key,),
                    }
                ]
            )
        return btns

    async def _clear_callback(self, call: InlineCall, chat_id: int):
        hist_key = "global_context" if self.config["global_memory"] else chat_id
        self._clear_history(hist_key)
        await call.edit(
            (
                self.strings["memory_cleared_global"]
                if hist_key == "global_context"
                else self.strings["memory_cleared"]
            ),
            reply_markup=None,
        )

    async def _bridge_log_cb(self, call: InlineCall, bridge_key: str):
        stored = self._bridge_logs.get(bridge_key, {})
        log_text = stored.get("log", "<i>нет данных.</i>")
        text = f"<b>выполненные действия:</b>\n<blockquote expandable>{log_text}</blockquote>"
        btns = [
            [{"text": "назад", "callback": self._bridge_back_cb, "args": (bridge_key,)}]
        ]
        await call.edit(text, reply_markup=btns)

    async def _bridge_back_cb(self, call: InlineCall, bridge_key: str):
        stored = self._bridge_logs.get(bridge_key, {})
        response_text = stored.get("response")
        if response_text:
            parts = bridge_key.rsplit(":", 1)
            cid = int(parts[0]) if parts[0].isdigit() else 0
            try:
                mid = int(parts[1]) if len(parts) > 1 else 0
            except:
                mid = 0
            buttons = self._get_inline_buttons(cid, mid)
            await call.edit(response_text, reply_markup=buttons)
        else:
            await call.delete()

    def _get_sorted_keys(self):
        valid_keys = []
        now = time.time()
        for key in self.api_keys:
            if self.key_cooldowns.get(str(key), 0) > now:
                continue
            if key not in self.key_model_map:
                valid_keys.append((key, 0, random.random()))
                continue
            tier = self.key_model_map[key]
            if tier == -1:
                continue
            valid_keys.append((key, tier, random.random()))
        valid_keys.sort(key=lambda x: (-x[1], x[2]))
        return [item[0] for item in valid_keys]

    async def _get_provider_model_catalog(self, provider: str) -> list:
        return self._provider_curated_models(provider)

    def _wmodel_build_view(self, uid: str, page: int, query: str) -> tuple:
        data = self._wmodel_cache.get(uid)
        if not data:
            return (
                "сессия истекла.",
                [
                    [
                        {
                            "text": "закрыть",
                            "callback": self._wmodel_close_cb,
                            "args": (uid,),
                            "style": "danger",
                        }
                    ]
                ],
            )
        models: list = data["models"]
        provider: str = data["provider"]
        PER_PAGE = 10
        filtered = [m for m in models if query.lower() in m.lower()] if query else models
        total = len(filtered)
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        page = max(0, min(page, total_pages - 1))
        current = self._resolve_effective_model(
            provider, self.config.get("model_name")
        )
        slice_ = filtered[page * PER_PAGE : (page + 1) * PER_PAGE]
        sub_parts = [f"{total} мод.", f"стр. {page + 1}/{total_pages}"]
        if query:
            sub_parts.append(f"поиск: {utils.escape_html(query)}")
        title = (
            f"<b>{utils.escape_html(self._provider_label(provider))}</b>\n"
            f"<i>{' · '.join(sub_parts)}</i>"
        )
        btns = []
        for m in slice_:
            mark = "* " if m == current else ""
            btns.append(
                [
                    {
                        "text": f"{mark}{m}",
                        "callback": self._wmodel_select_cb,
                        "args": (uid, m, page, query),
                    }
                ]
            )
        nav = []
        if page > 0:
            nav.append(
                {
                    "text": "<",
                    "callback": self._wmodel_page_cb,
                    "args": (uid, page - 1, query),
                }
            )
        nav.append({"text": f"{page + 1}/{total_pages}", "data": "witty:noop"})
        if page < total_pages - 1:
            nav.append(
                {
                    "text": ">",
                    "callback": self._wmodel_page_cb,
                    "args": (uid, page + 1, query),
                }
            )
        btns.append(nav)
        btns.append(
            [
                {
                    "text": "поиск",
                    "input": "введите часть названия модели",
                    "handler": self._wmodel_search_handler,
                    "kwargs": {"uid": uid},
                },
                {"text": "x", "callback": self._wmodel_close_cb, "args": (uid,), "style": "danger"},
            ]
        )
        return title, btns

    async def _wmodel_select_cb(
        self, call: InlineCall, uid: str, model: str, page: int, query: str
    ):
        provider = self._wmodel_cache.get(uid, {}).get(
            "provider", self._normalize_provider_name()
        )
        self.config["model_name"] = model
        self._remember_provider_model(provider, model)
        text, btns = self._wmodel_build_view(uid, page, query)
        await call.edit(text, reply_markup=btns)
        await call.answer(model, show_alert=False)

    async def _wmodel_page_cb(self, call: InlineCall, uid: str, page: int, query: str):
        text, btns = self._wmodel_build_view(uid, page, query)
        await call.edit(text, reply_markup=btns)

    async def _wmodel_search_handler(self, call: InlineCall, query: str, *, uid: str):
        text, btns = self._wmodel_build_view(uid, 0, query.strip())
        await call.edit(text, reply_markup=btns)

    async def _wmodel_close_cb(self, call: InlineCall, uid: str):
        self._wmodel_cache.pop(uid, None)
        await call.answer()
        try:
            await call.delete()
        except Exception:
            with contextlib.suppress(Exception):
                await self.client.delete_messages(call.chat_id, call.message_id)

    async def _send_to_deepai_api(self, model, messages, temperature):
        """запрос к deepai.org chat api без ключа (порт /root/ai.py)."""
        history = []
        system_chunks = []
        for msg in messages or []:
            role = str(msg.get("role") or "")
            content = msg.get("content")
            if isinstance(content, list):
                chunks = []
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") == "text":
                        chunks.append(str(part.get("text") or ""))
                    elif part.get("type") == "image_url":
                        chunks.append("[изображение]")
                content = "\n".join(c for c in chunks if c).strip()
            content = str(content or "").strip()
            if not content:
                continue
            if role == "system":
                system_chunks.append(content)
            elif role in ("user", "assistant"):
                history.append({"role": role, "content": content})
        if system_chunks:
            sys_text = "[System instruction]\n" + "\n\n".join(system_chunks)
            for i in range(len(history) - 1, -1, -1):
                if history[i]["role"] == "user":
                    history[i]["content"] = (
                        DEEPAI_DIRECTIVE
                        + "\n\n"
                        + history[i]["content"]
                        + "\n\n"
                        + sys_text
                    )
                    break
            else:
                history.insert(0, {"role": "user", "content": sys_text})
        fields = {
            "chatHistory": json.dumps(history, ensure_ascii=False),
            "model": str(model or DEEPAI_DEFAULT_MODEL),
            "session_uuid": str(uuid.uuid4()),
            "sensitivity_request_id": str(uuid.uuid4()),
            "tool_activity_support": "1",
            "thinking_image_tool_support": "1",
            "hacker_is_stinky": "very_stinky",
            "enabled_tools": '["image_generator","image_editor"]',
        }
        fields["web_access_enabled"] = "true"
        headers = {
            "api-key": _deepai_island_key(),
            "Origin": "https://deepai.org",
            "Referer": "https://deepai.org/chat",
            "User-Agent": DEEPAI_UA,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
        }
        cookie = os.environ.get("DEEPAI_COOKIE")
        if cookie:
            headers["Cookie"] = cookie
        proxy = self.config.get("proxy") or None
        text = ""
        async with aiohttp.ClientSession() as session:
            last_error = None
            for attempt in range(3):
                form = aiohttp.FormData()
                for name, value in fields.items():
                    form.add_field(name, str(value))
                try:
                    async with session.post(
                        DEEPAI_API_URL + "/hacking_is_a_serious_crime",
                        headers=headers,
                        data=form,
                        proxy=proxy,
                        timeout=aiohttp.ClientTimeout(total=120),
                    ) as resp:
                        text = await resp.text()
                        if resp.status < 500 and resp.status != 429:
                            break
                    last_error = RuntimeError(f"deepai HTTP {resp.status}")
                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    last_error = exc
                if attempt < 2:
                    await asyncio.sleep(2 * (attempt + 1))
            else:
                raise last_error or RuntimeError("deepai: запрос не удался")
            try:
                data = json.loads(text)
            except ValueError:
                data = None
            task_id = None
            if isinstance(data, dict):
                task_id = data.get("task_id")
                if not task_id:
                    err = data.get("err") or data.get("error")
                    if err:
                        raise RuntimeError(f"deepai: {err}")
            if not task_id:
                if isinstance(data, (dict, list, int, float)):
                    result = json.dumps(data, ensure_ascii=False)
                else:
                    result = str(text or "").strip()
                if not result:
                    raise ValueError("пустой ответ deepai")
                return result, {}
            deadline = time.time() + WITTY_TIMEOUT
            answer = ""
            while time.time() < deadline:
                async with session.get(
                    DEEPAI_API_URL + "/check_chat_task_status",
                    params={"type": "thinking-task", "task_id": task_id},
                    headers=headers,
                    proxy=proxy,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as poll_resp:
                    poll_resp.raise_for_status()
                    data = await poll_resp.json(content_type=None)
                answer = data.get("answer_text") or answer
                status = data.get("status")
                if status == "COMPLETED":
                    result = (answer or data.get("thinking_text") or "").strip()
                    if not result:
                        raise ValueError("пустой ответ deepai")
                    return result, {}
                if status == "FAILED":
                    raise RuntimeError("задача упала на стороне deepai")
                await asyncio.sleep(1)
            raise asyncio.TimeoutError()

    def _convert_google_history_to_openai(
        self, history: list, system_prompt: str
    ) -> list:
        """конвертирует историю из формата google в формат openai."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        user_tz = self._get_timezone()
        for item in history:
            role = "assistant" if item["role"] == "model" else "user"
            content = item.get("content", "")
            if "date" in item and item["date"]:
                dt = datetime.fromtimestamp(item["date"], user_tz)
                content = f"[{dt.strftime('%d.%m.%Y %H:%M')}] {content}"
            messages.append({"role": role, "content": content})
        return messages

    def _effective_system_prompt(self) -> str:
        parts = []
        if self.config.get("tg_bridge_enabled"):
            parts.append(TG_BRIDGE_GUIDE)
        base = self.config.get("system_instruction") or ""
        if base.strip():
            parts.append(base.strip())
        if True:
            parts.append(
                "You have access to web search. When you need current or real-time information"
                "(recent events, news, live data, facts you are uncertain about due to training cutoff),"
                "output ONLY the following on your very first line and nothing else:\n"
                "[SEARCH: your search query]\n"
                "The system will perform the search and provide results back to you."
                "For questions you can answer confidently from training data, respond normally without [SEARCH:]."
            )
        tools_prompt = self._build_api_tools_prompt()
        if tools_prompt:
            parts.append(tools_prompt)
        result = "\n\n".join(parts)
        return result.strip() or None

    async def _get_web_browser(self):
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError("playwright is not installed") from exc

        if self._web_browser and self._web_browser.is_connected():
            return self._web_browser
        if self._playwright is None:
            self._playwright = await async_playwright().start()
        try:
            self._web_browser = await self._playwright.chromium.launch(
                headless=True,
                args=(
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--no-first-run",
                    "--no-default-browser-check",
                ),
            )
        except BaseException:
            await self._stop_web_browser()
            raise
        return self._web_browser

    async def _stop_web_browser(self):
        browser, playwright = self._web_browser, self._playwright
        self._web_browser = None
        self._playwright = None
        if browser:
            with contextlib.suppress(Exception):
                await browser.close()
        if playwright:
            with contextlib.suppress(Exception):
                await playwright.stop()

    @staticmethod
    def _web_search_url(url: str) -> str:
        """Unwrap DuckDuckGo redirect links before opening them in Chromium."""
        if url.startswith("//"):
            url = "https:" + url
        parts = urlsplit(url)
        if "duckduckgo.com" in parts.netloc and parts.path.startswith("/l/"):
            target = parse_qs(parts.query).get("uddg", [""])[0]
            if target:
                return unquote(target)
        return url

    async def _fetch_urls_content(self, urls: list, max_chars: int = 2000) -> list:
        """Render result pages in Chromium and extract visible text."""
        if not urls:
            return []
        async with self._web_browser_lock:
            try:
                browser = await self._get_web_browser()
            except Exception as exc:
                logger.warning("witty: Chromium web fetch is unavailable: %s", exc)
                await self._stop_web_browser()
                return [""] * len(urls)

            async def fetch_one(raw_url: str) -> str:
                url = self._web_search_url(str(raw_url or ""))
                if not url.startswith(("http://", "https://")):
                    return ""
                page = None
                try:
                    page = await browser.new_page(
                        user_agent=(
                            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                        ),
                        viewport={"width": 1280, "height": 900},
                    )

                    async def skip_heavy_resources(route):
                        if route.request.resource_type in {"image", "media", "font"}:
                            await route.abort()
                        else:
                            await route.continue_()

                    await page.route(
                        "**/*",
                        skip_heavy_resources,
                    )
                    response = await page.goto(
                        url, wait_until="domcontentloaded", timeout=20000
                    )
                    if response and response.status >= 400:
                        return ""
                    with contextlib.suppress(Exception):
                        await page.wait_for_load_state("networkidle", timeout=5000)
                    text = await page.locator(
                        "main, article, [role='main'], body"
                    ).first.inner_text(timeout=5000)
                    return re.sub(r"\s+", " ", str(text or "")).strip()[:max_chars]
                except Exception as exc:
                    logger.debug("witty: Chromium fetch failed for %s: %s", url, exc)
                    return ""
                finally:
                    if page:
                        with contextlib.suppress(Exception):
                            await page.close()

            try:
                results = await asyncio.gather(
                    *[fetch_one(url) for url in urls], return_exceptions=True
                )
                return [result if isinstance(result, str) else "" for result in results]
            finally:
                await self._stop_web_browser()

    SEARXNG_INSTANCES = (
        "https://searx.be",
        "https://search.inetol.net",
        "https://searx.tiekoetter.com",
        "https://priv.au",
        "https://paulgo.io",
    )

    async def _searxng_search(self, query: str, max_results: int = 5) -> list:
        if not query or not query.strip():
            return []
        base = str(self.config.get("searxng_url") or "").strip().rstrip("/")
        instances = [base] if base else list(self.SEARXNG_INSTANCES)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            ),
            "Accept": "application/json",
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            for instance in instances:
                try:
                    async with session.get(
                        f"{instance}/search",
                        params={"q": query.strip(), "format": "json"},
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json(content_type=None)
                except Exception:
                    continue
                if not isinstance(data, dict):
                    continue
                results = []
                for item in (data.get("results") or [])[:max_results]:
                    if not isinstance(item, dict):
                        continue
                    title = str(item.get("title") or "").strip()
                    link = str(item.get("url") or "").strip()
                    snippet = str(item.get("content") or "").strip()
                    if title or link:
                        results.append(
                            {"title": title, "link": link, "snippet": snippet}
                        )
                if results:
                    return results
        return []

    async def _web_search(self, query: str, max_results: int = 5) -> list:
        results = await self._searxng_search(query, max_results)
        if not results:
            return await self._duckduckgo_search(query, max_results)
        urls = [r.get("link", "") for r in results if r.get("link")]
        if urls:
            page_contents = await self._fetch_urls_content(urls, max_chars=2000)
            for result, content in zip(results, page_contents):
                if content:
                    result["content"] = content
        return results

    async def _duckduckgo_search(self, query: str, max_results: int = 5) -> list:
        if not query or not query.strip():
            return []
        url = f"https://html.duckduckgo.com/html/?q={aiohttp.helpers.quote(query.strip())}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                "AppleWebKit/537.36 (KHTML, like Gecko)"
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    html = await resp.text()
        except Exception as e:
            logger.warning("witty: ddg search failed: %s", e)
            return []
        results = []
        for match in _DDG_TITLE_RE.finditer(html):
            link, title = match.group(1), match.group(2)
            title = _HTML_TAG_RE.sub("", title).replace("&nbsp;", "").strip()
            link = _HTML_TAG_RE.sub("", link).strip()
            results.append({"title": title, "link": link, "snippet": ""})
        for idx, match in enumerate(_DDG_SNIPPET_RE.finditer(html)):
            if idx >= len(results):
                break
            snippet = (
                _HTML_TAG_RE.sub("", match.group(1)).replace("&nbsp;", "").strip()
            )
            results[idx]["snippet"] = snippet
        results = results[:max_results]
        if results:
            urls = [r.get("link", "") for r in results]
            page_contents = await self._fetch_urls_content(urls, max_chars=2000)
            for result, content in zip(results, page_contents):
                if content:
                    result["content"] = content
        return results

    async def _resolve_tg_target(
        self, target, msg_obj: Message = None, reply_obj: Message = None
    ):
        if target is None or target == "current_chat":
            if isinstance(msg_obj, Message):
                return utils.get_chat_id(msg_obj)
            return None
        if target == "me":
            return "me"
        if target == "reply_user":
            if reply_obj and reply_obj.sender_id:
                return reply_obj.sender_id
            if msg_obj and isinstance(msg_obj, Message):
                try:
                    reply = await msg_obj.get_reply_message()
                    if reply and reply.sender_id:
                        return reply.sender_id
                except Exception:
                    pass
            return None
        if isinstance(target, int):
            return target
        if isinstance(target, str):
            s = target.strip()
            if s.lstrip("-").isdigit():
                return int(s)
            try:
                return await self.client.get_entity(s)
            except Exception:
                return None
        return None

    async def _execute_json_actions(
        self, actions, msg_obj: Message = None, reply_obj: Message = None
    ):
        results = []
        if not isinstance(actions, list):
            actions = [actions]
        for act in actions:
            if not isinstance(act, dict):
                continue
            action = str(act.get("action") or "").strip().lower()
            params = act.get("params") or {}
            try:
                if action == "telegram_send":
                    target = await self._resolve_tg_target(
                        params.get("target"), msg_obj, reply_obj
                    )
                    if not target:
                        raise ValueError("no target")
                    text = str(params.get("text") or "")
                    reply_to = params.get("reply_to")
                    silent = bool(params.get("silent", False))
                    media = (
                        params.get("media") or params.get("path") or params.get("url")
                    )
                    if media:
                        file_bytes = None
                        if str(media).startswith("http://") or str(media).startswith(
                            "https://"
                        ):
                            async with aiohttp.ClientSession() as session:
                                async with session.get(
                                    media, timeout=aiohttp.ClientTimeout(total=30)
                                ) as resp:
                                    file_bytes = await resp.read()
                        elif os.path.exists(media):
                            with open(media, "rb") as f:
                                file_bytes = f.read()
                        if not file_bytes:
                            raise ValueError("media not found")
                        file = io.BytesIO(file_bytes)
                        file.name = os.path.basename(str(media)) or "media"
                        sent = await self.client.send_file(
                            target, file, caption=text, reply_to=reply_to, silent=silent
                        )
                        results.append(
                            f"sent media to {params.get('target')} (msg {sent.id})"
                        )
                    else:
                        sent = await self.client.send_message(
                            target, text, reply_to=reply_to, silent=silent
                        )
                        results.append(
                            f"sent message to {params.get('target')} (msg {sent.id})"
                        )
                elif action == "telegram_edit":
                    target = await self._resolve_tg_target(
                        params.get("target"), msg_obj, reply_obj
                    )
                    message_id = int(params.get("message_id") or 0)
                    text = str(params.get("text") or "")
                    if not target or not message_id:
                        raise ValueError("target/message_id required")
                    await self.client.edit_message(target, message_id, text)
                    results.append(f"edited msg {message_id} in {params.get('target')}")
                elif action == "telegram_delete":
                    target = await self._resolve_tg_target(
                        params.get("target"), msg_obj, reply_obj
                    )
                    message_id = params.get("message_id") or params.get("message_ids")
                    if not target or not message_id:
                        raise ValueError("target/message_id required")
                    ids = (
                        [message_id]
                        if isinstance(message_id, int)
                        else list(message_id)
                    )
                    await self.client.delete_messages(target, ids)
                    results.append(
                        f"deleted {len(ids)} msg(s) in {params.get('target')}"
                    )
                elif action == "telegram_pin":
                    target = await self._resolve_tg_target(
                        params.get("target"), msg_obj, reply_obj
                    )
                    message_id = int(params.get("message_id") or 0)
                    silent = bool(params.get("silent", False))
                    if not target or not message_id:
                        raise ValueError("target/message_id required")
                    await self.client.pin_message(target, message_id, notify=not silent)
                    results.append(f"pinned msg {message_id} in {params.get('target')}")
                elif action == "telegram_unpin":
                    target = await self._resolve_tg_target(
                        params.get("target"), msg_obj, reply_obj
                    )
                    message_id = params.get("message_id")
                    if not target:
                        raise ValueError("target required")
                    if message_id:
                        await self.client.unpin_message(target, int(message_id))
                        results.append(
                            f"unpinned msg {message_id} in {params.get('target')}"
                        )
                    else:
                        await self.client.unpin_message(target)
                        results.append(f"unpinned all in {params.get('target')}")
                elif action == "telegram_forward":
                    target = await self._resolve_tg_target(
                        params.get("target"), msg_obj, reply_obj
                    )
                    from_target = await self._resolve_tg_target(
                        params.get("from_target"), msg_obj, reply_obj
                    )
                    message_id = int(params.get("message_id") or 0)
                    if not target or not from_target or not message_id:
                        raise ValueError("target/from_target/message_id required")
                    await self.client.forward_messages(target, message_id, from_target)
                    results.append(
                        f"forwarded msg {message_id} to {params.get('target')}"
                    )
                elif action == "telegram_reply":
                    target = await self._resolve_tg_target(
                        params.get("target"), msg_obj, reply_obj
                    )
                    message_id = int(params.get("message_id") or 0)
                    text = str(params.get("text") or "")
                    if not target or not message_id:
                        raise ValueError("target/message_id required")
                    sent = await self.client.send_message(
                        target, text, reply_to=message_id
                    )
                    results.append(
                        f"replied to msg {message_id} in {params.get('target')} (msg {sent.id})"
                    )
                elif action == "telegram_react":
                    target = await self._resolve_tg_target(
                        params.get("target"), msg_obj, reply_obj
                    )
                    message_id = int(params.get("message_id") or 0)
                    reaction = str(params.get("reaction") or "").strip()
                    if not target or not message_id or not reaction:
                        raise ValueError("target/message_id/reaction required")
                    await self.client(
                        tl_functions.messages.SendReactionRequest(
                            peer=target,
                            msg_id=message_id,
                            reaction=[tg_types.ReactionEmoji(emoticon=reaction)],
                        )
                    )
                    results.append(
                        f"reacted {reaction} to msg {message_id} in {params.get('target')}"
                    )
                elif action == "telegram_unreact":
                    target = await self._resolve_tg_target(
                        params.get("target"), msg_obj, reply_obj
                    )
                    message_id = int(params.get("message_id") or 0)
                    if not target or not message_id:
                        raise ValueError("target/message_id required")
                    await self.client(
                        tl_functions.messages.SendReactionRequest(
                            peer=target,
                            msg_id=message_id,
                            reaction=[],
                        )
                    )
                    results.append(
                        f"removed reactions from msg {message_id} in {params.get('target')}"
                    )
                elif action == "telegram_media_send":
                    target = await self._resolve_tg_target(
                        params.get("target"), msg_obj, reply_obj
                    )
                    if not target:
                        raise ValueError("no target")
                    media = (
                        params.get("path") or params.get("url") or params.get("media")
                    )
                    caption = str(params.get("caption") or "")
                    reply_to = params.get("reply_to")
                    if not media:
                        raise ValueError("path/url required")
                    file_bytes = None
                    fname = "media"
                    content_type = ""
                    if str(media).startswith("http://") or str(media).startswith(
                        "https://"
                    ):
                        async with aiohttp.ClientSession() as session:
                            async with session.get(
                                media, timeout=aiohttp.ClientTimeout(total=30)
                            ) as resp:
                                if resp.status != 200:
                                    raise ValueError(f"media download failed: HTTP {resp.status}")
                                file_bytes = await resp.read()
                                content_type = str(resp.headers.get("Content-Type") or "").lower()
                                fname = (
                                    os.path.basename(str(resp.url).split("?")[0]) or fname
                                )
                    elif os.path.exists(media):
                        with open(media, "rb") as f:
                            file_bytes = f.read()
                            fname = os.path.basename(media)
                    if not file_bytes:
                        raise ValueError("media not found")
                    if not os.path.splitext(fname)[1] and content_type.startswith("image/"):
                        ext = content_type.split(";", 1)[0].split("/", 1)[1]
                        fname += ".jpg" if ext == "jpeg" else f".{ext}"
                    file = io.BytesIO(file_bytes)
                    file.name = fname
                    try:
                        sent = await self.client.send_file(
                            target, file, caption=caption, reply_to=reply_to
                        )
                    except ImageProcessFailedError:
                        file.seek(0)
                        sent = await self.client.send_file(
                            target,
                            file,
                            caption=caption,
                            reply_to=reply_to,
                            force_document=True,
                        )
                    results.append(
                        f"sent media to {params.get('target')} (msg {sent.id})"
                    )
                elif action == "telegram_get_chat":
                    target = await self._resolve_tg_target(
                        params.get("target"), msg_obj, reply_obj
                    )
                    if not target:
                        raise ValueError("target required")
                    entity = await self.client.get_entity(target)
                    info = {
                        "id": getattr(entity, "id", "?"),
                        "title": getattr(entity, "title", "") or "",
                        "username": getattr(entity, "username", "") or "",
                        "is_group": bool(
                            getattr(entity, "megagroup", False)
                            or getattr(entity, "broadcast", False)
                        ),
                    }
                    if hasattr(entity, "participants_count"):
                        info["participants_count"] = entity.participants_count
                    lines = "\n".join(f"{k}: {v}" for k, v in info.items())
                    results.append(f"chat info for {target}:\n{lines}")
                elif action == "telegram_get_messages":
                    target = await self._resolve_tg_target(
                        params.get("target"), msg_obj, reply_obj
                    )
                    if not target:
                        raise ValueError("target required")
                    limit = max(1, min(100, int(params.get("limit") or 20)))
                    reply_to = params.get("reply_to")
                    messages = await self.client.get_messages(
                        target, limit=limit, reply_to=reply_to
                    )
                    lines = []
                    for m in messages:
                        sender = "?"
                        try:
                            sender = get_display_name(await m.get_sender())
                        except Exception:
                            pass
                        text_preview = (m.text or "[media]").replace("\n", "")[:80]
                        lines.append(f"[{m.id}] {sender}: {text_preview}")
                    results.append(f"recent messages in {target}:\n" + "\n".join(lines))
                elif action == "telegram_search":
                    target = await self._resolve_tg_target(
                        params.get("target"), msg_obj, reply_obj
                    )
                    query = str(params.get("query") or "").strip()
                    if not target or not query:
                        raise ValueError("target/query required")
                    limit = max(1, min(100, int(params.get("limit") or 20)))
                    messages = await self.client.get_messages(
                        target, limit=limit, search=query
                    )
                    lines = []
                    for m in messages:
                        sender = "?"
                        try:
                            sender = get_display_name(await m.get_sender())
                        except Exception:
                            pass
                        text_preview = (m.text or "[media]").replace("\n", "")[:80]
                        lines.append(f"[{m.id}] {sender}: {text_preview}")
                    results.append(
                        f"search'{query}'in {target} ({len(lines)} results):\n"
                        + "\n".join(lines)
                    )
                elif action == "shell":
                    command = str(params.get("command") or "").strip()
                    timeout = float(params.get("timeout") or 30)
                    cwd = params.get("cwd")
                    if not command:
                        raise ValueError("command required")
                    proc = await asyncio.create_subprocess_shell(
                        command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=cwd if cwd and os.path.isdir(cwd) else None,
                    )
                    try:
                        stdout, stderr = await asyncio.wait_for(
                            proc.communicate(), timeout=timeout
                        )
                    except asyncio.TimeoutError:
                        proc.kill()
                        with contextlib.suppress(Exception):
                            await proc.communicate()
                        raise RuntimeError("shell command timed out")
                    out = (
                        stdout.decode("utf-8", errors="replace")
                        + "\n"
                        + stderr.decode("utf-8", errors="replace")
                    ).strip()
                    out = out[:2000]
                    results.append(
                        f"shell output:\n<pre>{utils.escape_html(out)}</pre>"
                    )
                elif action == "update_profile":
                    first_name = params.get("first_name")
                    last_name = params.get("last_name")
                    about = params.get("about")
                    username = params.get("username")
                    if (
                        first_name is not None
                        or last_name is not None
                        or about is not None
                    ):
                        await self.client(
                            tl_functions.account.UpdateProfileRequest(
                                first_name=first_name,
                                last_name=last_name,
                                about=about,
                            )
                        )
                    if username is not None:
                        await self.client(
                            tl_functions.account.UpdateUsernameRequest(
                                username=str(username) or ""
                            )
                        )
                    results.append("profile updated")
                elif action == "update_profile_photo":
                    media = params.get("path") or params.get("url")
                    if not media:
                        raise ValueError("path/url required")
                    file_bytes = None
                    if str(media).startswith("http://") or str(media).startswith(
                        "https://"
                    ):
                        async with aiohttp.ClientSession() as session:
                            async with session.get(
                                media, timeout=aiohttp.ClientTimeout(total=30)
                            ) as resp:
                                file_bytes = await resp.read()
                    elif os.path.exists(media):
                        with open(media, "rb") as f:
                            file_bytes = f.read()
                    if not file_bytes:
                        raise ValueError("photo not found")
                    uploaded = await self.client.upload_file(io.BytesIO(file_bytes))
                    await self.client(
                        tl_functions.photos.UploadProfilePhotoRequest(file=uploaded)
                    )
                    results.append("profile photo updated")
                elif action == "telegram_get_profile":
                    target = await self._resolve_tg_target(
                        params.get("target"), msg_obj, reply_obj
                    )
                    if not target:
                        raise ValueError("target required")
                    entity = await self.client.get_entity(target)
                    info = {
                        "id": getattr(entity, "id", "?"),
                        "first_name": getattr(entity, "first_name", "") or "",
                        "last_name": getattr(entity, "last_name", "") or "",
                        "username": getattr(entity, "username", "") or "",
                        "is_bot": bool(getattr(entity, "bot", False)),
                        "is_premium": bool(getattr(entity, "premium", False)),
                    }
                    lines = "\n".join(f"{k}: {v}" for k, v in info.items())
                    results.append(f"profile of {target}:\n{lines}")
                elif action == "telegram_get_me":
                    entity = self.me
                    info = {
                        "id": getattr(entity, "id", "?"),
                        "first_name": getattr(entity, "first_name", "") or "",
                        "last_name": getattr(entity, "last_name", "") or "",
                        "username": getattr(entity, "username", "") or "",
                        "is_bot": bool(getattr(entity, "bot", False)),
                        "is_premium": bool(getattr(entity, "premium", False)),
                    }
                    lines = "\n".join(f"{k}: {v}" for k, v in info.items())
                    results.append(f"my profile:\n{lines}")
                elif action == "stop":
                    results.append("##STOP##")
                else:
                    results.append(f"unknown action: {action}")
            except Exception as e:
                results.append(f"action {action} failed: {utils.escape_html(str(e))}")
        return results

    def _api_tools_enabled(self) -> bool:
        return True

    def _get_api_tools_max_steps(self) -> int:
        try:
            return max(1, int(self.config.get("api_tools_max_steps") or 6))
        except (TypeError, ValueError):
            return 6

    def _get_api_tools_timeout(self) -> int:
        try:
            return max(1, min(600, int(self.config.get("api_tools_timeout") or 60)))
        except (TypeError, ValueError):
            return 60

    def _get_api_tools_output_chars(self) -> int:
        try:
            return max(
                1000,
                min(80000, int(self.config.get("api_tools_output_chars") or 12000)),
            )
        except (TypeError, ValueError):
            return 12000

    @staticmethod
    def _api_tool_action_name(value: str) -> str:
        aliases = {
            "bash": "shell",
            "sh": "shell",
            "shell": "shell",
            "terminal": "shell",
            "command": "shell",
            "run_command": "shell",
            "exec": "shell",
            "execute": "shell",
            "file.read": "file_read",
            "read_file": "file_read",
            "file_read": "file_read",
            "read": "file_read",
            "file.write": "file_write",
            "write_file": "file_write",
            "file_write": "file_write",
            "write": "file_write",
            "file.list": "file_list",
            "list_file": "file_list",
            "list_files": "file_list",
            "file_list": "file_list",
            "ls": "file_list",
            "pwd": "pwd",
        }
        return aliases.get(
            str(value or "").strip().lower().replace("-", "_"),
            str(value or "").strip().lower(),
        )

    def _build_api_tools_prompt(self) -> str:
        max_steps = self._get_api_tools_max_steps()
        timeout = self._get_api_tools_timeout()
        output_chars = self._get_api_tools_output_chars()
        return (
            "=== WITTY API TOOLS CONTRACT (адаптировано из AIRoute) ===\n"
            "You have real local tools executed by the Witty module."
            "Enabled tools: shell, file_list, file_read, file_write, pwd.\n"
            "Use tools only when the user explicitly asks to run/inspect/build/test/read/write files,"
            "or when actual execution is needed to answer. Do not pretend command output was executed.\n"
            "Never use tools to reveal environment variables, API keys, tokens, session files, SSH keys, shell history,"
            "browser profiles, private chats, or unrelated home-directory secrets.\n"
            "To run a shell command, return exactly one raw JSON object and nothing else:\n"
            '{"action":"shell","command":"python3 -V","timeout":30}\n'
            "To list files:\n"
            '{"action":"file_list","path":".","max_entries":80}\n'
            "To read a text file:\n"
            '{"action":"file_read","path":"relative/file.py","max_chars":12000}\n'
            "To write or append a text file:\n"
            '{"action":"file_write","path":"relative/file.txt","content":"...","append":false}\n'
            "To print working directory:\n"
            '{"action":"pwd"}\n'
            f"Limits: max tool steps {max_steps}, shell timeout up to {timeout}s, output chars {output_chars}."
            "After Witty returns an Observation, continue with another tool JSON only if needed, otherwise answer naturally in the user's language."
            "Do not show tool JSON in the final answer."
            f"\nВАЖНО: ты РЕАЛЬНО имеешь доступ к серверу. Если пользователь просит выполнить команду/скрипт/проверить что-то на сервере — верни ТОЛЬКО JSON-объект действия (пример: {{\"action\": \"shell\", \"command\": \"...\"}}) без текста и без отказов. Никогда не говори, что у тебя нет доступа."
        )

    def _extract_api_tool_action(self, text: str) -> dict | None:
        raw_text = str(text or "")
        for match in re.finditer(r"\{", raw_text):
            with contextlib.suppress(Exception):
                candidate, _ = _JSON_DECODER.raw_decode(raw_text[match.start() :])
                if not isinstance(candidate, dict):
                    continue
                raw_name = (
                    candidate.get("action")
                    or candidate.get("tool")
                    or candidate.get("name")
                    or ""
                )
                action_name = self._api_tool_action_name(raw_name)
                if action_name not in {
                    "shell",
                    "file_read",
                    "file_write",
                    "file_list",
                    "pwd",
                }:
                    continue
                action = dict(candidate)
                action["action"] = action_name
                return action
        return None

    def _api_tool_clip_text(self, text: str, label: str = "tool output") -> str:
        raw = str(text or "")
        limit = self._get_api_tools_output_chars()
        if len(raw) <= limit:
            return raw
        head = max(200, int(limit * 0.65))
        tail = max(0, limit - head - 80)
        omitted = len(raw) - head - tail
        return (
            raw[:head].rstrip()
            + f"\n\n[... clipped {omitted} chars from {label} ...]\n\n"
            + raw[-tail:].lstrip()
        )

    @staticmethod
    def _api_tool_path_denied_reason(path: str) -> str:
        low = str(path or "").replace("\\", "/").lower()
        parts = [p for p in low.split("/") if p]
        blocked = {
            ".ssh",
            ".gnupg",
            ".aws",
            ".gcloud",
            ".azure",
            ".docker",
            ".env",
            ".netrc",
            ".bash_history",
            ".zsh_history",
            "id_rsa",
            "id_dsa",
            "id_ecdsa",
            "id_ed25519",
            "authorized_keys",
            "known_hosts",
        }
        if any(p in blocked for p in parts):
            return "sensitive path is blocked"
        if any(p.endswith(".session") or p.endswith(".session-journal") for p in parts):
            return "session files are blocked"
        if any(t in low for t in ("secret", "token", "credential", "password")):
            return "secret-looking path is blocked"
        return ""

    def _api_tool_resolve_path(
        self, raw_path: str, allow_create: bool = False
    ) -> tuple[str, str]:
        workdir = os.path.realpath(os.getcwd())
        raw = str(raw_path or ".").strip()
        if raw.startswith("~") or os.path.isabs(os.path.expanduser(raw)):
            raise ValueError("absolute and home paths are not allowed")
        if "\x00" in raw:
            raise ValueError("invalid path")
        candidate = os.path.realpath(os.path.join(workdir, raw))
        try:
            inside = os.path.commonpath([workdir, candidate]) == workdir
        except ValueError:
            inside = False
        if not inside:
            raise ValueError("path outside workspace")
        rel = os.path.relpath(candidate, workdir)
        denied = self._api_tool_path_denied_reason(rel)
        if denied:
            raise ValueError(denied)
        if not allow_create and not os.path.exists(candidate):
            raise ValueError("path not found")
        return candidate, rel

    @staticmethod
    def _api_tool_shell_denied_reason(command: str) -> str:
        value = str(command or "").strip()
        if not value:
            return "command is required"
        low = value.lower()
        blocked_patterns = (
            r"(^|[;&|]\s*)(env|printenv)(\s|$)",
            r"\bos\.environ\b",
            r"\bgetenv\s*\(",
            r"\.session(?:-journal)?\b",
            r"(^|[^\w.-])\.env([^\w.-]|$)",
            r"/\.ssh\b|~/.ssh\b|id_rsa|id_ed25519|authorized_keys",
            r"\b(api[_-]?key|secret|token|password|credential)s?\b",
            r"\.bash_history|\.zsh_history",
        )
        for pattern in blocked_patterns:
            if re.search(pattern, low, flags=re.I):
                return "command looks like it may expose secrets or sessions"
        return ""

    async def _run_api_shell_tool(self, action: dict) -> dict:
        command = str(
            action.get("command") or action.get("cmd") or action.get("input") or ""
        ).strip()
        denied = self._api_tool_shell_denied_reason(command)
        if denied:
            raise RuntimeError(denied)
        timeout = self._get_api_tools_timeout()
        try:
            timeout = max(
                1,
                min(
                    self._get_api_tools_timeout(), int(action.get("timeout") or timeout)
                ),
            )
        except (TypeError, ValueError):
            pass
        cwd = None
        if action.get("cwd"):
            cwd, _ = self._api_tool_resolve_path(action["cwd"])
            if not os.path.isdir(cwd):
                raise ValueError("cwd is not a directory")
        executable = shutil.which("bash") or None
        proc = None
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd if cwd and os.path.isdir(cwd) else None,
                executable=executable,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            if proc is not None:
                with contextlib.suppress(Exception):
                    proc.kill()
                with contextlib.suppress(Exception):
                    await proc.communicate()
            raise RuntimeError(f"shell command timed out after {timeout}s") from exc
        stdout_text = self._api_tool_clip_text(
            stdout.decode("utf-8", errors="replace"), "stdout"
        )
        stderr_text = self._api_tool_clip_text(
            stderr.decode("utf-8", errors="replace"), "stderr"
        )
        return {
            "observation": {
                "ok": int(proc.returncode or 0) == 0,
                "type": "shell",
                "command": command,
                "returncode": int(proc.returncode or 0),
                "stdout": stdout_text,
                "stderr": stderr_text,
            }
        }

    async def _run_api_file_list_tool(self, action: dict) -> dict:
        path, rel = self._api_tool_resolve_path(
            action.get("path") or action.get("dir") or ".", allow_create=True
        )
        if os.path.exists(path) and not os.path.isdir(path):
            raise ValueError("path is not a directory")
        if not os.path.exists(path):
            await asyncio.to_thread(os.makedirs, path, exist_ok=True)
        max_entries = 80
        try:
            max_entries = max(
                1, min(300, int(action.get("max_entries") or action.get("limit") or 80))
            )
        except (TypeError, ValueError):
            pass

        def _do_scandir():
            _entries = []
            with os.scandir(path) as iterator:
                for entry in iterator:
                    if len(_entries) >= max_entries:
                        break
                    denied = self._api_tool_path_denied_reason(
                        os.path.join(rel, entry.name)
                    )
                    if denied:
                        continue
                    with contextlib.suppress(OSError):
                        st = entry.stat()
                        _entries.append(
                            {
                                "name": entry.name,
                                "path": os.path.normpath(os.path.join(rel, entry.name)),
                                "type": "dir" if entry.is_dir() else "file",
                                "size": int(st.st_size),
                            }
                        )
            _entries.sort(key=lambda item: (item["type"] != "dir", item["name"].lower()))
            return _entries

        entries = await asyncio.to_thread(_do_scandir)
        return {
            "observation": {
                "ok": True,
                "type": "file_list",
                "path": "." if rel == "." else rel,
                "entries": entries,
            }
        }

    async def _run_api_file_read_tool(self, action: dict) -> dict:
        path, rel = self._api_tool_resolve_path(
            action.get("path") or action.get("file") or ""
        )
        if not os.path.isfile(path):
            raise RuntimeError("path is not a file")
        max_chars = min(self._get_api_tools_output_chars(), 12000)
        try:
            max_chars = max(
                200,
                min(
                    self._get_api_tools_output_chars(),
                    int(action.get("max_chars") or action.get("chars") or max_chars),
                ),
            )
        except (TypeError, ValueError):
            pass

        def _do_read():
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                return handle.read(max_chars + 1)

        content = await asyncio.to_thread(_do_read)
        clipped = len(content) > max_chars
        if clipped:
            content = content[:max_chars]
        return {
            "observation": {
                "ok": True,
                "type": "file_read",
                "path": rel,
                "chars": len(content),
                "clipped": clipped,
                "content": content,
            }
        }

    async def _run_api_file_write_tool(self, action: dict) -> dict:
        path, rel = self._api_tool_resolve_path(
            action.get("path") or action.get("file") or "", allow_create=True
        )
        if os.path.isdir(path):
            raise RuntimeError("path is a directory")
        content = str(
            action.get("content") if action.get("content") is not None else ""
        )
        append = str(action.get("append") or "").lower() in {"true", "1", "yes"}
        parent_dir = os.path.dirname(path) or os.getcwd()
        mode = "a" if append else "w"

        def _do_write():
            os.makedirs(parent_dir, exist_ok=True)
            with open(path, mode, encoding="utf-8") as handle:
                handle.write(content)

        await asyncio.to_thread(_do_write)
        return {
            "observation": {
                "ok": True,
                "type": "file_write",
                "path": rel,
                "bytes": len(content.encode("utf-8")),
                "append": append,
            }
        }

    async def _run_api_tool_action(self, action: dict) -> dict:
        action_name = self._api_tool_action_name(
            action.get("action") or action.get("tool") or action.get("name") or ""
        )
        if action_name == "pwd":
            return {
                "observation": {
                    "ok": True,
                    "type": "pwd",
                    "cwd": os.path.abspath(os.getcwd()),
                }
            }
        if action_name == "shell":
            return await self._run_api_shell_tool(action)
        if action_name == "file_list":
            return await self._run_api_file_list_tool(action)
        if action_name == "file_read":
            return await self._run_api_file_read_tool(action)
        if action_name == "file_write":
            return await self._run_api_file_write_tool(action)
        raise RuntimeError(f"unknown api tool action: {action_name}")

    async def _run_api_tools_agent_loop_openai(
        self,
        *,
        provider: str,
        target_model: str,
        base_messages: list,
        temperature: float,
        progress_state: dict = None,
    ) -> dict:
        tool_prompt = self._build_api_tools_prompt()
        if not tool_prompt:
            return {"text": "", "agent_log": []}

        max_steps = self._get_api_tools_max_steps()
        logs = []
        messages = [dict(message) for message in base_messages]
        system_idx = next(
            (i for i, m in enumerate(messages) if m.get("role") == "system"), None
        )
        if system_idx is not None:
            messages[system_idx]["content"] = (
                str(messages[system_idx]["content"] or "") + "\n\n" + tool_prompt
            )
        else:
            messages.insert(0, {"role": "system", "content": tool_prompt})

        for step in range(1, max_steps + 1):
            if progress_state is not None:
                progress_state["phase"] = f"tool step {step}/{max_steps}: calling model..."
            raw_text, _ = await self._send_to_deepai_api(
                target_model, messages, temperature
            )

            action = self._extract_api_tool_action(raw_text)
            if not action:
                return {"text": raw_text or "", "agent_log": logs}

            action_name = self._api_tool_action_name(action.get("action"))
            target = (
                action.get("command") or action.get("path") or action.get("file") or "."
            )
            if progress_state is not None:
                progress_state["phase"] = f"tool step {step}/{max_steps}: {action_name}..."
                progress_state["log"].append(f"step {step}: {action_name}: {str(target)[:80]}")
            try:
                execution = await self._run_api_tool_action(action)
            except Exception as exc:
                execution = {
                    "observation": {
                        "ok": False,
                        "type": action_name,
                        "error": str(exc)[:1200],
                    }
                }

            observation = execution.get("observation") or {
                "ok": False,
                "error": "empty observation",
            }
            ok_label = "ok" if observation.get("ok") else "error"
            logs.append(f"{action_name}: {str(target)[:140]} -> {ok_label}")
            if progress_state is not None:
                progress_state["log"].append(f"  -> {ok_label}")

            messages.append({"role": "assistant", "content": raw_text or ""})
            messages.append(
                {
                    "role": "user",
                    "content": "Observation:"
                    + json.dumps(observation, ensure_ascii=False),
                }
            )

        return {
            "text": "api tools выполнились, но модель продолжала вызывать инструменты. повтори запрос короче или уточни команду.",
            "agent_log": logs,
        }

    _WCFG_LABELS = {
        "model_name": "модель",
        "system_instruction": "системный промпт",
        "max_history_length": "длина истории",
        "global_memory": "общая память",
        "interactive_buttons": "кнопки ответа",
        "inline_pagination": "пагинация",
        "temperature": "температура",
        "timezone": "часовой пояс",
        "proxy": "прокси",
        "websearch_max_results": "результатов поиска",
        "searxng_url": "searxng url",
        "tg_bridge_enabled": "telegram bridge",
        "show_tokens": "показывать токены",
        "show_time": "показывать время",
        "api_tools_max_steps": "api tools шаги",
        "api_tools_timeout": "api tools таймаут",
        "api_tools_output_chars": "api tools вывод",
    }

    _WCFG_BOOL_KEYS = frozenset(
        {
            "interactive_buttons",
            "global_memory",
            "show_tokens",
            "show_time",
            "inline_pagination",
            "tg_bridge_enabled",
        }
    )
    _WCFG_NUMBER_KEYS = frozenset(
        {
            "max_history_length",
            "temperature",
            "websearch_max_results",
            "api_tools_max_steps",
            "api_tools_timeout",
            "api_tools_output_chars",
        }
    )

    def _cfg_value_text(self, key: str) -> str:
        value = self.config.get(key)
        if isinstance(value, bool):
            return "on" if value else "off"
        if value is None or value == "":
            return "(не задано)"
        s = str(value)
        if len(s) > 30:
            s = s[:27] + "..."
        return s

    @loader.command()
    async def wcfg(self, message: Message):
        """[provider|section] - инлайн-меню настроек witty."""
        args = utils.get_args_raw(message).strip()
        if args:
            section = {"module": "interface"}.get(args.lower(), args.lower())
            text, btns = self._wacfg_section_view(section)
        else:
            text, btns = self._wacfg_home_view()
        await self.inline.form(text=text, message=message, reply_markup=btns)

    _WACFG_SECTIONS = {
        "basic": (
            "основное",
            [
                "system_instruction",
                "temperature",
                "timezone",
                "proxy",
            ],
        ),
        "memory": ("память", ["max_history_length", "global_memory"]),
        "search": ("поиск", ["websearch_max_results", "searxng_url"]),
        "interface": (
            "интерфейс",
            [
                "interactive_buttons",
                "inline_pagination",
                "show_tokens",
                "show_time",
            ],
        ),
        "tools": (
            "api tools",
            [
                "api_tools_max_steps",
                "api_tools_timeout",
                "api_tools_output_chars",
            ],
        ),
        "bridge": ("telegram bridge", ["tg_bridge_enabled"]),
    }

    def _wacfg_home_view(self):
        provider = self._normalize_provider_name()
        effective = self._resolve_effective_model(provider, self.config["model_name"])
        label = self._provider_label(provider)
        lines = [
            "<b>Witty / Настройки</b>",
            "<blockquote>",
            f"Провайдер: <code>{utils.escape_html(label)}</code>",
            f"Модель: <code>{utils.escape_html(effective)}</code>",
            "</blockquote>",
            "",
            "Выберите раздел:",
        ]
        section_button = lambda key: {
            "text": self._WACFG_SECTIONS[key][0],
            "callback": self._wacfg_section_cb,
            "args": (key,),
        }
        btns = [
            [section_button("basic"), section_button("memory")],
            [section_button("search")],
            [section_button("interface"), section_button("tools")],
            [section_button("bridge")],
            [
                {
                    "text": "закрыть",
                    "callback": self._wacfg_close_cb,
                    "style": "danger",
                }
            ],
        ]
        return "\n".join(lines), btns

    async def _wacfg_section_cb(self, call: InlineCall, section: str):
        text, btns = self._wacfg_section_view(section)
        await call.edit(text, reply_markup=btns)

    def _wacfg_section_view(self, section: str):
        title, keys = self._WACFG_SECTIONS.get(section, (f"{section}", []))
        lines = [f"<b>{utils.escape_html(title)}</b>", "", "Нажмите на параметр, чтобы изменить его."]
        btns = []
        for key in keys:
            label = self._WCFG_LABELS.get(key, key)
            value = self._cfg_value_text(key)
            meta = self._wacfg_field_meta(key)
            ftype = meta.get("type", "string")
            if ftype == "bool":
                is_on = bool(self.config.get(key))
                btns.append(
                    [
                        {
                            "text": f"{label}: {'вкл' if is_on else 'выкл'}",
                            "callback": self._wacfg_toggle_section_cb,
                            "args": (section, key),
                            "style": "success" if is_on else "danger",
                        }
                    ]
                )
            elif ftype == "number":
                btns.append(
                    [
                        {
                            "text": f"{label}: {value}",
                            "input": f"введите числовое значение для {label}",
                            "handler": self._wacfg_input_handler,
                            "kwargs": {"key": key, "section": section},
                        }
                    ]
                )
            else:
                btns.append(
                    [
                        {
                            "text": f"{label}: {value}",
                            "input": f"введите новое значение для {label} (- чтобы очистить)",
                            "handler": self._wacfg_input_handler,
                            "kwargs": {"key": key, "section": section},
                        }
                    ]
                )
        btns.append([{"text": "назад", "callback": self._wacfg_home_cb}])
        return "\n".join(lines), btns

    def _wacfg_field_meta(self, key: str) -> dict:
        if key in self._WCFG_BOOL_KEYS:
            return {"type": "bool"}
        if key in self._WCFG_NUMBER_KEYS:
            return {"type": "number"}
        return {"type": "string"}

    async def _wacfg_toggle_section_cb(self, call: InlineCall, section: str, key: str):
        self.config[key] = not bool(self.config.get(key))
        text, btns = self._wacfg_section_view(section)
        await call.edit(text, reply_markup=btns)

    async def _wacfg_input_handler(
        self,
        call: InlineCall,
        query: str,
        *,
        key: str,
        section: str = None,
        provider: str = None,
    ):
        value = query.strip()
        if not value:
            return await call.answer("пустое значение", show_alert=True)
        meta = self._wacfg_field_meta(key)
        if value == "-" and meta["type"] == "string":
            value = ""
        try:
            if meta["type"] == "number":
                value = float(value) if "." in value else int(value)
                if key == "temperature":
                    value = max(0.0, min(2.0, float(value)))
                elif key == "max_history_length":
                    value = max(0, int(value))
                elif key == "websearch_max_results":
                    value = max(1, min(10, int(value)))
                elif key == "api_tools_max_steps":
                    value = max(1, min(20, int(value)))
                elif key == "api_tools_timeout":
                    value = max(1, min(600, int(value)))
                elif key == "api_tools_output_chars":
                    value = max(1000, min(80000, int(value)))
        except ValueError:
            return await call.answer("некорректное число", show_alert=True)
        if key == "model_name" and provider:
            value = str(value).strip() or self._provider_default_model(provider)
            if self._normalize_provider_name(provider) == self._normalize_provider_name():
                self.config[key] = value
            self._remember_provider_model(provider, value)
        else:
            self.config[key] = value
        await call.answer(f"{self._WCFG_LABELS.get(key, key)} обновлено")
        if section:
            text, btns = self._wacfg_section_view(section)
        else:
            text, btns = self._wacfg_home_view()
        await call.edit(text, reply_markup=btns)

    async def _wacfg_home_cb(self, call: InlineCall):
        text, btns = self._wacfg_home_view()
        await call.edit(text, reply_markup=btns)

    async def _wacfg_close_cb(self, call: InlineCall):
        try:
            await self.client.delete_messages(call.chat_id, call.message_id)
        except Exception:
            await call.edit("меню закрыто.", reply_markup=None)

    def _extract_json_actions(self, text: str) -> list:
        """AIRoute-style: extract ALL valid action dicts using raw_decode"""
        raw_text = str(text or "")
        actions = []
        seen = set()
        for match in re.finditer(r"\{", raw_text):
            with contextlib.suppress(Exception):
                obj, _ = _JSON_DECODER.raw_decode(raw_text[match.start() :])
                if isinstance(obj, dict) and "action" in obj and obj["action"]:
                    key = json.dumps(obj, sort_keys=True)
                    if key not in seen:
                        seen.add(key)
                        actions.append(obj)
        if not actions:
            for match in re.finditer(r"\[", raw_text):
                with contextlib.suppress(Exception):
                    obj, _ = _JSON_DECODER.raw_decode(raw_text[match.start() :])
                    if isinstance(obj, list):
                        for item in obj:
                            if isinstance(item, dict) and item.get("action"):
                                key = json.dumps(item, sort_keys=True)
                                if key not in seen:
                                    seen.add(key)
                                    actions.append(item)
        return actions

    @staticmethod
    def _strip_json(text: str) -> str:
        text = re.sub(r"```json\s*.*?\s*```", "", text, flags=re.DOTALL)
        while True:
            cleaned = False
            for match in re.finditer(r"\{", text):
                with contextlib.suppress(Exception):
                    obj, consumed = _JSON_DECODER.raw_decode(text[match.start() :])
                    if isinstance(obj, dict) and obj.get("action"):
                        end = match.start() + consumed
                        while end < len(text) and text[end] in " \t\n\r,]":
                            end += 1
                        if end < len(text) and text[end] == "]":
                            end += 1
                        text = text[: match.start()] + text[end:]
                        cleaned = True
                        break
                    elif isinstance(obj, list):
                        end = match.start() + consumed
                        text = text[: match.start()] + text[end:]
                        cleaned = True
                        break
            if not cleaned:
                break
        return text.strip()

    def _is_memory_enabled(self, chat_id: str) -> bool:
        return chat_id not in self.memory_disabled_chats
