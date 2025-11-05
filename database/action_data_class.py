import datetime
from typing import Literal

from sqlalchemy import select, insert, update, column, text, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database.model import (ChannelsTable, MediaTable)


class DataInteraction():
    def __init__(self, session: async_sessionmaker):
        self._sessions = session

    async def add_channel(self, channel_id: int, title: str, city: str, time: datetime.time):
        async with self._sessions() as session:
            result = await session.execute(insert(ChannelsTable).values(
                channel_id=channel_id,
                title=title,
                city=city,
                time=time
            ).returning(ChannelsTable.id))
            await session.commit()
        return result.scalar()

    async def add_media(self, path: str, type: Literal['photo', 'video', 'animation']):
        async with self._sessions() as session:
            await session.execute(insert(MediaTable).values(
                path=path,
                type=type
            ))
            await session.commit()

    async def get_medias(self):
        async with self._sessions() as session:
            result = await session.scalars(select(MediaTable))
        return result.fetchall()

    async def get_media(self, id: int):
        async with self._sessions() as session:
            result = await session.scalar(select(MediaTable).where(MediaTable.id == id))
        return result

    async def get_channels(self):
        async with self._sessions() as session:
            result = await session.scalars(select(ChannelsTable))
        return result.fetchall()

    async def get_channel(self, id: int):
        async with self._sessions() as session:
            result = await session.scalar(select(ChannelsTable).where(ChannelsTable.id == id))
        return result

    async def update_channel(self, id: int, column: str, value: any):
        async with self._sessions() as session:
            await session.execute(update(ChannelsTable).where(ChannelsTable.id == id).values(
                {column: value}
            ))
            await session.commit()

    async def del_channel(self, id: int):
        async with self._sessions() as session:
            await session.execute(delete(ChannelsTable).where(ChannelsTable.id == id))
            await session.commit()

    async def del_media(self, id: int):
        async with self._sessions() as session:
            await session.execute(delete(MediaTable).where(MediaTable.id == id))
            await session.commit()
