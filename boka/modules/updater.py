# ©️ Dan Gazizullin, 2021-2023
# This file is a part of Hikka Userbot
# 🌐 https://github.com/hikariatama/Hikka
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

# Fully hardened build: every update / auto-download / auto-install / remote
# poll in the upstream Updater module has been removed.
# This userbot is fully standalone: it never talks to GitHub, never runs git,
# never touches pip, and never fetches remote state.

import logging

from .. import loader, utils
from .._internal import restart

logger = logging.getLogger(__name__)

__all__ = ["UpdaterMod"]


@loader.tds
class UpdaterMod(loader.Module):
    """Updates are disabled in this hardened build"""

    strings = {"name": "Updater"}
    strings_ru = {"name": "Апдейтер"}

    @staticmethod
    def _disabled():
        return "🛡 <b>Обновления и авто-загрузки отключены в защищённой сборке.</b>"

    @loader.command()
    async def changelog(self, message):
        """Show update history — disabled"""
        await utils.answer(message, self._disabled())

    @loader.command()
    async def update(self, message):
        """Update the userbot — disabled"""
        await utils.answer(message, self._disabled())

    @loader.command()
    async def rollback(self, message):
        """Rollback the userbot — disabled"""
        await utils.answer(message, self._disabled())

    @loader.command()
    async def autoupdate(self, message):
        """Toggle auto-update — disabled"""
        await utils.answer(message, self._disabled())

    @loader.command()
    async def source(self, message):
        """Get userbot source — disabled"""
        await utils.answer(message, self._disabled())

    @loader.command()
    async def restart(self, message):
        """Restart the userbot (local only, no updates)"""
        await utils.answer(message, "🔄 <b>Перезапуск…</b>")
        restart()

    @loader.command()
    async def ubstop(self, message):
        """Stop the userbot immediately (local only)"""
        await utils.answer(message, "🛑 <b>Остановка…</b>")
        from .._internal import die

        die()