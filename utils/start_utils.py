from datetime import datetime, date, time

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from services.media_storage import MediaStorage
from utils.schedulers import create_channel_post
from database.action_data_class import DataInteraction


async def start_schedulers(bot: Bot, session: DataInteraction, scheduler: AsyncIOScheduler, media_storage: MediaStorage):
    for channel in await session.get_channels():
        job_id = f'channel_task_{channel.id}'
        scheduler.add_job(
            create_channel_post,
            'interval',
            args=[channel.channel_id, 8005178596, bot, session, media_storage],
            id=job_id,
            next_run_time=datetime.combine(date.today(), channel.time),
            hours=24
        )