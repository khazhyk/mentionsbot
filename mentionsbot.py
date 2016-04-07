import discord
from discord.ext.commands import Bot, when_mentioned
import config
import re
import sys
import os
import io
import signal
import logging
import asyncio


class MentionsBot(Bot):
    """MentionsBot is a bot that private messages users when they are mentioned.

    MentionsBot is primarily meant to be used on a per-server basis, with opt-out
    per user. However, a user can opt-in to recieve mentions and they will recieve
    them for all servers shared with mentionsbot.
    """

    pattern = re.compile("@everyone", re.IGNORECASE)

    def send_message(self, destination, content, *args, **kwargs):
        """Overwrite send_message to prevent @everyone mentions."""
        content = self.pattern.sub("@\u200beveryone", content)[:2000]

        return super().send_message(destination, content, *args, **kwargs)

    async def say_briefly(self, content, time, *args, **kwargs):
        """Helper command to delete a message after sending it."""
        message = await self.say(content, *args, **kwargs)
        await asyncio.sleep(time)
        await self.delete_message(message)

    async def dispatch_über_ready(self):
        while True:
            if self.do_not_dispatch_über_ready:
                self.do_not_dispatch_über_ready = False
                await asyncio.sleep(2)
            self.dispatch("über_ready")
            return

    async def on_server_available(self, server):
        self.do_not_dispatch_über_ready = True

    async def on_ready(self):
        """Start a task that will try to dispatch über_ready."""
        self.do_not_dispatch_über_ready = True
        asyncio.ensure_future(self.dispatch_über_ready())

    async def on_über_ready(self):
        """When servers have stopped loading."""
        # Load up our stuff
        print("über_ready")
        self.load_extension("track_mentions")


def bare_pms(bot, message):
    if message.channel.is_private:
        return ""
    return when_mentioned(bot, message)


def run():
    if os.name == "nt":
        sys.stdout = io.TextIOWrapper(
            sys.stdout.detach(), encoding=sys.stdout.encoding,
            errors="backslashreplace", line_buffering=True)
        sys.stderr = io.TextIOWrapper(
            sys.stderr.detach(), encoding=sys.stderr.encoding,
            errors="backslashreplace", line_buffering=True)

    if hasattr(os, 'getpgrp'):
        f = open('mentionsbot.pgid', 'w')
        f.write(str(os.getpgrp()))
        f.close()

    def signal_handler(singal, frame):
        del singal, frame
        f = open('mentionsbot.pid', 'w')
        f.close()
        print("Got signal, killing everything")
        os._exit(0)  # kill everyone

    tmlog = logging.getLogger("track_mentions")

    tmlog.setLevel(logging.DEBUG)
    tmlog.addHandler(logging.StreamHandler())

    signal.signal(signal.SIGINT, signal_handler)

    instance = MentionsBot(command_prefix=bare_pms)
    instance.remove_command("help")

    instance.run('token', config.token)

if __name__ == "__main__":
    run()
