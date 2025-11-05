import asyncio
import os
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, Message, FSInputFile
from aiogram_dialog import DialogManager
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from utils.ai_utils import get_answer_by_prompt
from database.action_data_class import DataInteraction


async def update_storage_media(storage, session: DataInteraction):
    media_id = storage.get_current_media()
    media = await session.get_media(media_id)
    try:
        os.remove(media.path)
    except Exception:
        ...
    await session.del_media(media.id)
    await storage.set_current_media(None)
    await storage.configurate_media()


async def create_channel_post(channel_id: int, user_id: int, bot: Bot, session: DataInteraction,
                              media_storage):
    channel = await session.get_channel(channel_id)
    text = await get_answer_by_prompt(channel.city)
    text = f'<b>Доброе утро, {channel.city}!</b>\n\n' + text
    media_id = media_storage.get_current_media()
    try:
        if media_id:
            media = await session.get_media(media_id)
            if media.type == 'photo':
                await bot.send_photo(
                    chat_id=channel.channel_id,
                    photo=FSInputFile(path=media.path),
                    caption=text
                )
            elif media.type == 'animation':
                await bot.send_animation(
                    chat_id=channel.channel_id,
                    animation=FSInputFile(path=media.path),
                    caption=text
                )
            else:
                await bot.send_video(
                    chat_id=channel.channel_id,
                    video=FSInputFile(path=media.path),
                    caption=text
                )
        else:
            await bot.send_message(channel.channel_id,  text)
    except Exception as err:
        print(err)
        await bot.send_message(
            chat_id=user_id,
            text=f'Во время выкладки поста в канал {channel.title} произошла какая-то ошибка, '
                 f'пожалуйста выложите пост вручную'
        )


