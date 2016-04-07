from .track_mentions import TrackMentionsCog
import asyncio
from aiopg.sa import create_engine
import config
import random

async def real_setup(bot):
    engine = await create_engine(config.database)
    control_channel = bot.get_channel(TrackMentionsCog.control_channel_id)
    TrackMentionsCog.nonce = "{}".format(random.randint(-2**63, 2**63))
    await bot.send_message(control_channel, "New instance starting up... Bugger off old instances! " + TrackMentionsCog.nonce)
    bot.add_cog(TrackMentionsCog(bot, engine))
    # Find control channel, send message


def setup(bot):
    asyncio.ensure_future(real_setup(bot))
