import discord
import asyncio
import datetime
import logging
from discord.ext.commands import command, check
from .database import Configuration, MentionsMode, MentionsEnabled
import config

log = logging.getLogger(__name__)

HELP_TEXT = """\
Hi! I'm MentionsBot! I can private message you are mentioned while you are offline or idle so you don't lose them in the scrollback!

I can also be set to *catalog* mode, in which case I'll PM you whenever you are mentioned, online or not. (Off by default)

Server administrators can enable me for users thier server by running "{me.mention} server enabled".
If you would like to disable me, just run "{me.mention} server disabled".

Even if I'm not enabled server-wide, individual users can opt in or out of recieving messages from me, so just having me hanging around is still handy!
Users which wish to be private messaged by me, even if it's not enabled server-wide, can send me the message "user mode enabled".
If you really don't want to get any messages from me, send me the message "user mode disabled".
If you only want to recieve messages for servers which have enabled it server-wide, but not other servers, send me "user mode default"

If you would like to enable or disable catalog mode, send me "user catalog true" or "user catalog false".

Admins may use "{me.mention} server" to see current server configuration, and users may private message me "user" to see current user configuration."""


def check_permissions(**perms):
    def pred(ctx):
        msg = ctx.message

        ch = msg.channel
        author = msg.author
        resolved = ch.permissions_for(author)
        return all(getattr(resolved, name, None) == value for name, value in perms.items())
    return check(pred)


class TrackMentionsCog():
    def __init__(self, bot, engine):
        self.bot = bot
        self.pending = {}
        self._pending_lock = asyncio.Lock()
        self.configuration = Configuration(engine)

    # ---------------------------------------------- #
    # Listeners
    # ---------------------------------------------- #

    async def on_message(self, message):
        """Process a message."""
        if message.channel.is_private:
            return

        if len(message.mentions) == 0:
            return

        # Check if pm mentions is enabled server-wide
        server_enabled = await self._server_enabled(message.server)

        if len(message.mentions) > 10:
            log.error("Dropped message with more than 10 mentions!: {}".format(message.content))
            return

        for mention in message.mentions:
            if mention == self.bot.user:
                continue

            # Tri-bool per user - enabled, disabled, default
            user_enabled = await self._user_enabled(mention, default=server_enabled)

            if user_enabled:
                user_mode = await self._user_mode(mention)

                # Now, based on usermode and user status, either dispatch an update, queue a possible update, or discard

                if user_mode is MentionsMode.Catalog:
                    # In catalog mode, send *all* mentions
                    await self._send_mention(mention, message)
                elif user_mode is MentionsMode.Normal:
                    if (mention.status is discord.Status.idle or
                       mention.status is discord.Status.offline):
                        # In normal mode, send immediately if they are offline.
                        await self._send_mention(mention, message)

        print(message.clean_content)

    # ---------------------------------------------- #
    # Helpers
    # ---------------------------------------------- #

    async def _send_mention(self, user: discord.User, message: discord.Message):
        """Send a message regarding someone getting mentioned."""
        log.debug("Sending mention to user: {}, {}".format(user, message.clean_content))
        await self.bot.send_message(user,
"""You were mentioned by {message.author.name} ({message.author.mention}) on {message.channel.mention} in {message.server.name}
(type `user mode disabled` if you would like to stop recieving these, or `help` for more info about the bot.)
{message.clean_content}""".format(message=message))

    async def _server_enabled(self, server: discord.Server):
        return (await self.configuration.get_server(server)).enabled

    async def _user_enabled(self, user: discord.User, default: bool):
        return (await self.configuration.get_user(user)).enabled

    async def _user_mode(self, user: discord.User):
        return (await self.configuration.get_user(user)).mentions_mode

    # ---------------------------------------------- #
    # Configuration Commands.
    # ---------------------------------------------- #

    @command(pass_context=True, no_pm=True)
    @check_permissions(manage_server=True)
    async def server(self, ctx, setting=None):
        """Manage server configuration. Need to have permission to manage server."""
        if setting is None:
            server_conf = await self.configuration.get_server(ctx.message.server)

            if server_conf.enabled is MentionsEnabled.Enabled:
                await self.bot.say("This server is currently configured to private message offline and idle members when they get mentioned.")
            else:
                await self.bot.say("This server is currently configured to only private message opted-in members when they get mentioned.")
        else:
            if setting.lower() == "enabled":
                await self.configuration.update_server(ctx.message.server, enabled=MentionsEnabled.Enabled)
            elif setting.lower() == "disabled":
                await self.configuration.update_server(ctx.message.server, enabled=MentionsEnabled.Disabled)
            else:
                await self.bot.say("You may only choose 'enabled' or 'disabled'")
                return
            await self.bot.say("Updated!")

    @command(pass_context=True)
    async def user(self, ctx, key=None, setting=None):
        """Manage user configuration. Only allowed via PM."""
        if not ctx.message.channel.is_private:
            return

        if key is None:
            conf = await self.configuration.get_user(ctx.message.author)

            msg = ""
            if conf.enabled is MentionsEnabled.Enabled:
                msg += "You will be private messaged whenever you are mentioned on a server I can see."
            elif conf.enabled is MentionsEnabled.Default:
                msg += "You will be private messaged whenever you are mentioned on a server whose admins have enabled me for thier users."
            else:
                await self.bot.say("You will not recieve private messages from me when you are mentioned.")
                return
            if conf.mentions_mode is MentionsMode.Normal:
                msg += "\nYou will only recieve private messages when you are idle or offline"
            else:
                msg += "\nYou have enabled 'catalog' mode: you will recieve a private message **every** time I see you mentioned"

            await self.bot.say(msg)

        else:
            key = key.lower()
            if key not in ['catalog', 'mode']:
                await self.bot.say("The only available configuration options are 'catalog' and 'mode'")
                return

            if setting is None:
                if key == 'catalog':
                    await self.bot.say("cataloging may be set to `true` or `false`")
                else:
                    await self.bot.say("Mode may be `enabled`, `disabled`, or `default`")
                return

            setting = setting.lower()
            if key == 'catalog':
                if setting not in ['true', 'false']:
                    await self.bot.say("Catalog can only be set to 'true' or 'false'")
                    return

                if setting == 'true':
                    await self.configuration.update_user(ctx.message.author, mentions_mode=MentionsMode.Catalog)
                else:
                    await self.configuration.update_user(ctx.message.author, mentions_mode=MentionsMode.Normal)
                await self.bot.say("Updated!")

            elif key == 'mode':
                if setting not in ['enabled', 'disabled', 'default']:
                    await self.bot.say("Mode may be: 'enabled', 'disabled', or 'default'")
                    return

                if setting == 'enabled':
                    await self.configuration.update_user(ctx.message.author, enabled=MentionsEnabled.Enabled)
                elif setting == 'disabled':
                    await self.configuration.update_user(ctx.message.author, enabled=MentionsEnabled.Disabled)
                else:
                    await self.configuration.update_user(ctx.message.author, enabled=MentionsEnabled.Default)
                await self.bot.say("Updated!")

    @command()
    async def help(self):
        await self.bot.say(HELP_TEXT.format(me=self.bot.user))
