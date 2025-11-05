import asyncio
import random

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from utils.schedulers import update_storage_media
from database.action_data_class import DataInteraction


class MediaStorage():
    def __init__(self, session: DataInteraction, scheduler: AsyncIOScheduler):
        self.session = session
        self.scheduler = scheduler
        self._current_media: int | None = None

    async def configurate_media(self):
        if self._current_media is not None:
            return
        medias = await self.session.get_medias()
        if not medias:
            async def polling_medias(storage: MediaStorage, session: DataInteraction, interval: int = 30):
                while True:
                    medias = await session.get_medias()
                    if medias:
                        await storage.configurate_media()
                        break
                    await asyncio.sleep(interval)
                return
            task = asyncio.create_task(polling_medias(self, self.session))
            return
        media = random.choice(list(medias))
        self.set_current_media(media.id)
        job = self.scheduler.get_job(job_id='update_media_process')
        if not job:
            self.scheduler.add_job(
                update_storage_media,
                'cron',
                args=[self, self.session],
                hour=0,
                minute=0,
                id='update_media_process'
            )

    def set_current_media(self, media_id: int | None):
        self._current_media = media_id

    def get_current_media(self) -> int | None:
        return self._current_media