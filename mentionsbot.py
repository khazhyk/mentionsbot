import discord
from discord.ext.commands import Bot, when_mentioned
import config
import re
import sys
import os
import io
import signal
import logging


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
        f = open('spoo.pgid', 'w')
        f.write(str(os.getpgrp()))
        f.close()

    def signal_handler(singal, frame):
        del singal, frame
        f = open('spoo.pid', 'w')
        f.close()
        print("Got signal, killing everything")
        os._exit(0)  # kill everyone

    tmlog = logging.getLogger("track_mentions")

    tmlog.setLevel(logging.DEBUG)
    tmlog.addHandler(logging.StreamHandler())

    signal.signal(signal.SIGINT, signal_handler)

    instance = MentionsBot(command_prefix=bare_pms)
    instance.remove_command("help")

    instance.load_extension("track_mentions")

    instance.user = discord.User(name="Mentions", id="167340110243823616", discriminator="1294", avatar="c4acf304bb7dfd70661aa3ca219b0a50")

    instance.run('token', config.token)

if __name__ == "__main__":
    run()
