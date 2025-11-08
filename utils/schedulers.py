import asyncio
import os
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, Message, FSInputFile
from aiogram_dialog import DialogManager
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from utils.ai_utils import get_answer_by_prompt
from database.action_data_class import DataInteraction


logger = logging.getLogger(__name__)


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
    counter = 0
    while True:
        if counter >= 5:
            await bot.send_message(
                chat_id=user_id,
                text=f'Во время выкладки поста в канал {channel.title} произошла какая-то ошибка генерации текста, '
                     f'пожалуйста выложите пост вручную'
            )
            return
        try:
            text = await get_answer_by_prompt(channel.city)
            break
        except Exception as err:
            logger.warning(f'deepseek generation error: {err}')
            await asyncio.sleep(5)
            counter += 1

    text = f'<b>Доброе утро, {channel.city}!</b>\n\n' + text
    media_id = media_storage.get_current_media()
    if media_id:
        counter = 0
        while True:
            media = await session.get_media(media_id)
            try:
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
                break
            except Exception:
                if counter >= 3:
                    try:
                        await bot.send_message(
                            chat_id=channel.channel_id,
                            text=text
                        )
                    except Exception:
                        await bot.send_message(
                            chat_id=user_id,
                            text=f'Во время выкладки поста в канал {channel.title} произошла какая-то ошибка, '
                                 f'пожалуйста выложите пост вручную'
                        )
                    break
                try:
                    os.remove(media.path)
                except Exception:
                    ...
                await session.del_media(media.id)
                await media_storage.update_media()
                media_id = media_storage.get_current_media()
                counter += 1
    else:
        try:
            await bot.send_message(
                chat_id=channel.channel_id,
                text=text
            )
        except Exception:
            await bot.send_message(
                chat_id=user_id,
                text=f'Во время выкладки поста в канал {channel.title} произошла какая-то ошибка, '
                     f'пожалуйста выложите пост вручную'
            )


