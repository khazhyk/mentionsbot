import sqlalchemy as sa
from enum import Enum
import discord


class MentionsMode(Enum):
    Catalog = 0
    Normal = 1


class MentionsEnabled(Enum):
    Default = 0
    Enabled = 1
    Disabled = 2


class UserConfig:
    __slots__ = ["mentions_mode", "enabled"]

    def __init__(self, mentions_mode, enabled):
        self.mentions_mode = mentions_mode
        self.enabled = enabled

UserConfig.default = UserConfig(MentionsMode.Normal, MentionsEnabled.Default)

UserConfigTable = sa.Table('user_config', sa.MetaData(),
                           sa.Column('id', sa.String, primary_key=True),
                           sa.Column('mentions_mode', sa.Integer),
                           sa.Column('enabled', sa.Integer))


class ServerConfig:
    __slots__ = ["enabled"]

    def __init__(self, enabled):
        self.enabled = enabled

ServerConfig.default = ServerConfig(False)

ServerConfigTable = sa.Table('server_config', sa.MetaData(),
                             sa.Column('id', sa.String, primary_key=True),
                             sa.Column('enabled', sa.Integer))


class Configuration:
    """Manages per server/per user configuration."""
    __slots__ = ["_cache", "engine"]

    def __init__(self, engine):
        """Engine should be aiopg.sa engine."""
        self._cache = dict()
        self.engine = engine

    # -------------------------------------------------- #
    # Database Operations
    # -------------------------------------------------- #

    async def _fetch_server(self, server: discord.Server):
        async with self.engine.acquire() as conn:
            res = await conn.execute(sa.select([ServerConfigTable.c.enabled]).where(ServerConfigTable.c.id == server.id).limit(1))
            val = await res.scalar()

        return ServerConfig(MentionsEnabled(val)) if val else ServerConfig.default

    async def _fetch_user(self, user: discord.User):
        async with self.engine.acquire() as conn:
            res = await conn.execute(sa.select([UserConfigTable.c.mentions_mode, UserConfigTable.c.enabled]).where(UserConfigTable.c.id == user.id).limit(1))
            val = await res.fetchone()

        if val:
            return UserConfig(MentionsMode(val[0]), MentionsEnabled(val[1]))
        return UserConfig.default

    async def _upsert_server(self, server: discord.Server, server_config: ServerConfig):
        async with self.engine.acquire() as conn:
            res = await conn.execute(ServerConfigTable.update().values(enabled=server_config.enabled.value).where(ServerConfigTable.c.id == server.id))

            if res.rowcount == 0:
                await conn.execute(ServerConfigTable.insert().values(enabled=server_config.enabled.value, id=server.id))

    async def _upsert_user(self, user: discord.User, user_config: UserConfig):
        async with self.engine.acquire() as conn:
            res = await conn.execute(UserConfigTable.update().values(mentions_mode=user_config.mentions_mode.value, enabled=user_config.enabled.value).where(UserConfigTable.c.id == user.id))

            if res.rowcount == 0:
                await conn.execute(UserConfigTable.insert().values(mentions_mode=user_config.mentions_mode.value, enabled=user_config.enabled.value, id=user.id))

    # -------------------------------------------------- #
    # Getting/updating configurations
    # -------------------------------------------------- #

    async def get_server(self, server):
        """Get a server config from the cache. Fetch from DB if needed."""
        if server.id not in self._cache:
            self._cache[server.id] = await self._fetch_server(server)

        return self._cache[server.id]

    async def get_user(self, user):
        """Get a user config from the cache. Fetch from DB if needed."""
        if user.id not in self._cache:
            self._cache[user.id] = await self._fetch_user(user)

        return self._cache[user.id]

    async def update_server(self, server, **kwargs):
        """Update server config in cache and database."""
        curr_config = await self.get_server(server)

        curr_config.enabled = kwargs.get('enabled', curr_config.enabled)

        await self._upsert_server(server, curr_config)

    async def update_user(self, user, **kwargs):
        """Update user config in cache and database."""
        curr_config = await self.get_user(user)

        curr_config.mentions_mode = kwargs.get('mentions_mode', curr_config.mentions_mode)
        curr_config.enabled = kwargs.get('enabled', curr_config.enabled)

        await self._upsert_user(user, curr_config)
