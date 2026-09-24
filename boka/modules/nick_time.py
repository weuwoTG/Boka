import re
from datetime import datetime

from boka_tl.tl.functions.account import UpdateProfileRequest

from .. import loader, utils


@loader.tds
class NickTimeMod(loader.Module):
    """Живое время в нике. .time — включить, .time off — выключить. Только для владельца."""

    strings = {"name": "NickTime"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "name",
                "",
                lambda: "Базовое имя без времени. Пусто — взять из текущего ника",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "format",
                "%H:%M",
                lambda: "Формат времени (strftime), напр. %H:%M или %H:%M:%S",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "timezone",
                "",
                lambda: "Часовой пояс (напр. Europe/Moscow). Пусто — время сервера",
                validator=loader.validators.String(),
            ),
        )

    @loader.loop(interval=60, autostart=False)
    async def _nick_loop(self):
        await self._tick()

    async def _now(self):
        tz = self.config["timezone"]
        if tz:
            try:
                from zoneinfo import ZoneInfo

                return datetime.now(ZoneInfo(tz))
            except Exception:
                pass
        return datetime.now()

    def _clean(self, name: str) -> str:
        return re.sub(r"\s*\[[^\]]*\]\s*$", "", name or "").strip()

    async def _base_name(self):
        me = await self._client.get_me()
        base = (
            self.config["name"]
            or self.get("base_name")
            or self._clean(me.first_name)
        )
        if not base:
            base = str(me.id)
        return base

    async def _tick(self):
        base = await self._base_name()
        target = f"{base} [{(await self._now()).strftime(self.config['format'])}]"
        me = await self._client.get_me()
        if me.first_name != target:
            await self._client(UpdateProfileRequest(first_name=target))

    @loader.command(alias="время")
    async def time(self, message):
        """- Живое время в нике (.time off — выключить). Только для владельца."""
        if getattr(message, "sender_id", None) != self.tg_id:
            return

        args = utils.get_args_raw(message).strip().lower()
        if args in {"off", "stop", "стоп", "выкл"}:
            self._nick_loop.stop()
            me = await self._client.get_me()
            base = self.config["name"] or self._clean(me.first_name)
            if base and me.first_name != base:
                await self._client(UpdateProfileRequest(first_name=base))
            await utils.answer(message, "🚫 Часы в нике выключены.")
            return

        base = await self._base_name()
        self.set("base_name", base)
        if not self._nick_loop.status:
            self._nick_loop.start()
            await self._tick()
        target = f"{base} [{(await self._now()).strftime(self.config['format'])}]"
        await utils.answer(message, f"✅ Часы в нике включены: <code>{utils.escape_html(target)}</code>")