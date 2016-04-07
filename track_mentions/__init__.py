from .track_mentions import TrackMentionsCog
import asyncio
from aiopg.sa import create_engine
import config

async def real_setup(bot):
    engine = await create_engine(config.database)
    bot.add_cog(TrackMentionsCog(bot, engine))


def setup(bot):
    asyncio.ensure_future(real_setup(bot))
