import os
from pathlib import Path

from aiogram import Bot
from aiogram.types import PhotoSize, Video, Animation


async def download_image(photo: PhotoSize, bot: Bot) -> str | None:
    if not os.path.exists('medias'):
        os.mkdir('medias')
    temp_photo_path = f"medias/temp_{photo.file_unique_id}.jpg"

    try:
        await bot.download(file=photo.file_id, destination=temp_photo_path)
        return temp_photo_path
    except Exception:
        return None


async def download_video(video: Video | Animation, bot: Bot) -> str | None:
    if not os.path.exists('medias'):
        os.mkdir('medias')

    file_info = await bot.get_file(video.file_id)
    file_path = file_info.file_path

    # Определяем расширение файла
    if isinstance(video, Animation):
        # Для анимаций используем .gif
        file_extension = '.gif'
    else:
        # Для видео используем оригинальное расширение или .mp4 по умолчанию
        file_extension = Path(file_path).suffix if Path(file_path).suffix else '.mp4'

    # Создаем имя файла
    if hasattr(video, 'file_name') and video.file_name:
        filename = video.file_name
        # Если у файла неправильное расширение, исправляем его
        if not filename.lower().endswith(file_extension.lower()):
            name_without_ext = os.path.splitext(filename)[0]
            filename = f"{name_without_ext}{file_extension}"
    else:
        filename = f"temp_{video.file_unique_id}{file_extension}"

    save_path = f'medias/{filename}'

    try:
        await bot.download_file(file_path, save_path)
    except Exception as err:
        print(err)
        return None

    return save_path


async def upload_media(media: PhotoSize | Video | Animation, bot: Bot) -> str | None:
    if isinstance(media, PhotoSize):
        return await download_image(media, bot)
    else:
        return await download_video(media, bot)


async def upload_medias(medias: list[PhotoSize | Video | Animation], bot: Bot) -> list[str]:
    saves = []
    for media in medias:
        if isinstance(media, PhotoSize):
            media = await download_image(media, bot)
        else:
            media = await download_video(media, bot)
        if not media:
            continue
        saves.append(media)
    return saves
