import logging
import os
import time
from contextlib import asynccontextmanager
from typing import List

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from grafana import RenderJob
from init import read_yaml, init_grafana, init_notifier, init_jobslist


def register_jobs(scheduler: AsyncIOScheduler, jobs: List[RenderJob]):
    for job in jobs:
        try:
            scheduler.add_job(func=job.notice, trigger=CronTrigger.from_crontab(job.crontab_cfg),)
            logging.info(f"任务 {job.name} 已添加")
        except Exception as e:
            logging.debug(e)
            raise f"任务 {job} 添加失败。"


def register_clean_job(scheduler: AsyncIOScheduler):
    expiry_days: int = read_yaml('config/config.yaml').get('files').get("expiry_days")

    def clean_files(days, directory):
        expiry_in = time.time() - (days * 86400)
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            file_creation_time = os.path.getctime(file_path)
            if file_creation_time < expiry_in:
                print(f"Deleting file: {file_path}")
                os.remove(file_path)

    crontab = "0 0 * * *"
    scheduler.add_job(
        func=clean_files,
        trigger=CronTrigger.from_crontab(crontab),
        kwargs={"days": expiry_days, "directory": 'files'}
    )


@asynccontextmanager
async def lifespan(myapp: FastAPI):
    scheduler = AsyncIOScheduler()

    # 初始化
    server_public_url: str = read_yaml('config/config.yaml').get('files').get('public_url')
    grafana_client = init_grafana()
    enable_notifiers = init_notifier()
    jobs = init_jobslist(grafana_client, enable_notifiers, server_public_url)

    register_jobs(scheduler, jobs)
    register_clean_job(scheduler)

    scheduler.start()

    yield

    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)
app.mount("/files", StaticFiles(directory="files"), name="files")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
