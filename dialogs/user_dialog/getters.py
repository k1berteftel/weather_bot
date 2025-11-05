import os
from datetime import datetime, date, time, timedelta

from aiogram.types import CallbackQuery, User, Message, PhotoSize, Video, ContentType
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.api.entities import MediaAttachment
from aiogram_dialog.widgets.kbd import Button, Select
from aiogram_dialog.widgets.input import ManagedTextInput, MessageInput
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from services.media_storage import MediaStorage
from utils.schedulers import create_channel_post
from utils.upload_utils import upload_media, upload_medias
from database.action_data_class import DataInteraction
from config_data.config import load_config, Config
from states.state_groups import startSG

config: Config = load_config()


async def channels_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    channels = await session.get_channels()
    if channels:
        text = 'Ваши каналы:\n'
        counter = 1
        for channel in channels:
            text += f'({counter}) {channel.title} - {channel.city} ({channel.time.strftime("%H:%M")})'
            counter += 1
    else:
        text = 'У вас не добавлено каналов'
    return {
        'text': text
    }


async def get_channel(msg: Message, widget: ManagedTextInput, dialog_manager: DialogManager, text: str):
    await msg.delete()
    try:
        chat_id = int(text)
    except Exception:
        if text.startswith('@'):
            chat_id = text
        else:
            fragments = text.split('/')
            if len(fragments) <= 1:
                await msg.answer('Отправленное вами сообщение не является ссылкой, юзернеймом или айдишником, '
                                 'пожалуйста попробуйте еще раз')
                return
            chat_id = '@' + fragments[-1]
    try:
        chat = await msg.bot.get_chat(chat_id)
    except Exception:
        await msg.answer('К сожалению такого канала не найдено или вы не добавили бота в канал c '
                         'админскими правами, пожалуйста попробуйте снова')
        return
    dialog_manager.dialog_data['channel_id'] = chat.id
    dialog_manager.dialog_data['title'] = chat.title
    await dialog_manager.switch_to(startSG.get_city)


async def get_city(msg: Message, widget: ManagedTextInput, dialog_manager: DialogManager, text: str):
    dialog_manager.dialog_data['city'] = text
    await dialog_manager.switch_to(startSG.get_time)


async def get_time(msg: Message, widget: ManagedTextInput, dialog_manager: DialogManager, text: str):
    try:
        time = datetime.strptime(text, '%H:%M').time()
    except Exception:
        await msg.answer('Вы ввели время не в том формате, пожалуйста попробуйте еще раз')
        return
    channel_id = dialog_manager.dialog_data.get('channel_id')
    title = dialog_manager.dialog_data.get('title')
    city = dialog_manager.dialog_data.get('city')
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    channel_id = await session.add_channel(channel_id, title, city, time)
    scheduler: AsyncIOScheduler = dialog_manager.middleware_data.get('scheduler')
    job_id = f'channel_task_{channel_id}'
    job = scheduler.get_job(job_id=job_id)
    if job:
        job.remove()
    media_storage: MediaStorage = dialog_manager.middleware_data.get('media_storage')
    scheduler.add_job(
        create_channel_post,
        'interval',
        args=[channel_id, msg.from_user.id, msg.bot, session, media_storage],
        id=job_id,
        next_run_time=datetime.combine(date.today(), time),
        hours=24
    )
    dialog_manager.dialog_data.clear()
    await msg.answer('✅Канал был успешно добавлен')
    await dialog_manager.switch_to(startSG.channels)


async def choose_channel_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    channels = await session.get_channels()
    buttons = []
    for channel in channels:
        buttons.append(
            (f'{channel.title} ({channel.time.strftime("%H:%M")})', channel.id)
        )
    buttons = [buttons[i:i + 10] for i in range(0, len(buttons), 10)]

    page = dialog_manager.dialog_data.get('channel_page')
    if not page:
        page = 0
        dialog_manager.dialog_data['channel_page'] = page
    current_buttons = buttons[page] if buttons else []

    not_first = False
    not_last = False
    if page != 0:
        not_first = True
    if len(buttons) and page != len(buttons) - 1:
        not_last = True

    return {
        'items': current_buttons,
        'page': f'{page + 1}/{len(buttons)}',
        'channels': bool(buttons),
        'not_first': not_first,
        'not_last': not_last
    }


async def channels_pager(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    page = dialog_manager.dialog_data.get('channel_page')
    action = clb.data.split('_')[0]
    if action == 'back':
        page -= 1
    else:
        page += 1
    dialog_manager.dialog_data['channel_page'] = page
    await dialog_manager.switch_to(startSG.choose_channel)


async def channel_selector(clb: CallbackQuery, widget: Select, dialog_manager: DialogManager, item_id: str):
    dialog_manager.dialog_data['channel_id'] = int(item_id)
    await dialog_manager.switch_to(startSG.channel_menu)


async def channel_menu_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    channel_id = dialog_manager.dialog_data.get('channel_id')
    channel = await session.get_channel(channel_id)
    text = (f'ℹ️Данные по каналу:\n<blockquote>\tКанал: {channel.title}\n\tГород: {channel.city}\n'
            f'\tВремя выхода поста: {channel.time.strftime("%H:%M")}</blockquote>')
    return {
        'text': text
    }


async def del_channel(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    channel_id = dialog_manager.dialog_data.get('channel_id')
    await session.del_channel(channel_id)
    dialog_manager.dialog_data.clear()
    await clb.answer('✅Канал был успешно удален')

    scheduler: AsyncIOScheduler = dialog_manager.middleware_data.get('scheduler')
    job_id = f'channel_task_{channel_id}'
    job = scheduler.get_job(job_id=job_id)
    if job:
        job.remove()

    await dialog_manager.switch_to(startSG.choose_channel)


async def change_time(msg: Message, widget: ManagedTextInput, dialog_manager: DialogManager, text: str):
    try:
        time = datetime.strptime(text, '%H:%M').time()
    except Exception:
        await msg.answer('Вы ввели время не в том формате, пожалуйста попробуйте еще раз')
        return
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    channel_id = dialog_manager.dialog_data.get('channel_id')
    await session.update_channel(channel_id, 'time', time)

    scheduler: AsyncIOScheduler = dialog_manager.middleware_data.get('scheduler')
    job_id = f'channel_task_{channel_id}'
    job = scheduler.get_job(job_id=job_id)
    if job:
        job.remove()
    media_storage: MediaStorage = dialog_manager.middleware_data.get('media_storage')
    scheduler.add_job(
        create_channel_post,
        'interval',
        args=[channel_id, msg.from_user.id, msg.bot, session, media_storage],
        id=job_id,
        next_run_time=datetime.combine(date.today(), time),
        hours=24
    )
    await dialog_manager.switch_to(startSG.channel_menu)


async def medias_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    medias = await session.get_medias()
    if medias:
        text = f'У вас добавлено: {len(medias)}'
    else:
        text = 'У вас не добавлено медиа'
    return {
        'text': text
    }


async def get_media(msg: Message, widget: MessageInput, dialog_manager: DialogManager):
    medias = dialog_manager.dialog_data.get('medias')
    if msg.photo:
        medias.append(msg.photo[-1])
    elif msg.video:
        medias.append(msg.video)
    elif msg.animation:
        medias.append(msg.animation)
    else:
        await msg.delete()
        await msg.answer('❗️Допускаются только форматы фото и видео')
    await dialog_manager.switch_to(startSG.get_medias, show_mode=ShowMode.DELETE_AND_SEND)


async def get_medias_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    medias = dialog_manager.dialog_data.get('medias')
    if not medias:
        medias = []
        dialog_manager.dialog_data['medias'] = medias
    return {
        'medias': len(medias)
    }


async def clean_media(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    medias = dialog_manager.dialog_data.get('medias')
    if not medias:
        await clb.answer('У вас пока не добавлено никаких медиа')
        return
    dialog_manager.dialog_data.clear()
    await dialog_manager.switch_to(startSG.get_medias, show_mode=ShowMode.DELETE_AND_SEND)


async def add_media(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    medias = dialog_manager.dialog_data.get('medias')
    if not medias:
        await clb.answer('У вас пока не добавлено никаких медиа')
        return
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    wait_msg = await clb.message.answer('Начался процесс сохранения медиа, пожалуйста ожидайте')
    for media in medias:
        path = await upload_media(media, clb.bot)
        type = 'photo' if isinstance(media, PhotoSize) else 'video' if isinstance(media, Video) else 'animation'
        await session.add_media(path, type)
    try:
        await wait_msg.delete()
    except Exception:
        ...
    await clb.message.answer('Медиа были успешно добавлены в общий реестр')
    dialog_manager.dialog_data.clear()
    await dialog_manager.switch_to(startSG.medias)


async def watch_medias_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    medias = await session.get_medias()
    page = dialog_manager.dialog_data.get('media_page')
    if not page:
        page = 0
        dialog_manager.dialog_data['media_page'] = page
    not_first = False
    not_last = False
    if page != 0:
        not_first = True
    if len(medias) and page != len(medias) - 1:
        not_last = True

    if medias:
        media = MediaAttachment(path=medias[page].path, type=medias[page].type)
    else:
        media = None

    return {
        'media': media,
        'page': f'{page + 1}/{len(medias)}',
        'not_first': not_first,
        'not_last': not_last
    }


async def medias_pager(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    page = dialog_manager.dialog_data.get('media_page')
    action = clb.data.split('_')[0]
    if action == 'back':
        page -= 1
    else:
        page += 1
    dialog_manager.dialog_data['media_page'] = page
    await dialog_manager.switch_to(startSG.watch_medias)


async def del_media(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    medias = await session.get_medias()
    page = dialog_manager.dialog_data.get('media_page')
    try:
        os.remove(medias[page].path)
    except Exception:
        ...
    await session.del_media(medias[page].id)
    dialog_manager.dialog_data.clear()
    await dialog_manager.switch_to(startSG.watch_medias)
