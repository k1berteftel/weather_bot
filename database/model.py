import datetime
from typing import Literal

from sqlalchemy import BigInteger, VARCHAR, ForeignKey, DateTime, Boolean, Column, Integer, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs


class Base(AsyncAttrs, DeclarativeBase):
    pass


class ChannelsTable(Base):
    __tablename__ = 'channels'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    channel_id: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(VARCHAR)
    city: Mapped[str] = mapped_column(VARCHAR)
    time: Mapped[datetime.time] = mapped_column(Time)


class MediaTable(Base):
    __tablename__ = 'media'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    path: Mapped[str] = mapped_column(VARCHAR)
    type: Mapped[Literal['photo', 'video', 'animation']] = mapped_column(VARCHAR)

