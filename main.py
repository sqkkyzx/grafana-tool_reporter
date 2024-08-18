import logging
import os
import time
from contextlib import asynccontextmanager
from typing import List, Literal

import uvicorn
import yaml
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from grafana import Grafana, render_and_send
import notifier


def read_yaml(filepath):
    with open(filepath, 'r', encoding='utf-8') as file:
        try:
            # 加载YAML内容
            data = yaml.safe_load(file)
            return data
        except yaml.YAMLError as exc:
            logging.error(f"Error in yaml file: {exc}")
            raise f"Cannot load {filepath}, please check file."


PUBLIC_URL = read_yaml('config/config.yaml').get('files').get('public_url')


def init_grafana():
    grafana_config: dict = read_yaml('config/config.yaml').get('grafana')
    return Grafana(**grafana_config)


def init_notifier():
    notifiers_config: dict = read_yaml('config/notifier.yaml')
    provided_notifiers: list[str] = list(notifiers_config.keys())
    notifiers = {}
    for notifier_type in provided_notifiers:
        notifier_class = getattr(notifier, notifier_type)
        if notifier_class:
            notifiers[notifier_type] = notifier_class(**notifiers_config.get(notifier_type))
        else:
            logging.warning(f'Provided Notifiers [{notifier_type}] not suppord.')
    if notifiers == {}:
        raise 'No provided notifier.'
    else:
        return notifiers


def init_jobslist(notifiers_validator: list):
    jobs_info = read_yaml('config/job.yaml').get('jobs')

    class JobPage(BaseModel):
        dashboard_uid: str
        panel_uid: int | None = None
        query: int | None = None

    class JobNotifier(BaseModel):
        type: str
        receiver: List[str]

        @field_validator('type')
        def validate_type(cls, value):
            if value not in notifiers_validator:
                raise ValueError(f"Selected notifier [{value}] is not been init.")
            return value

    class JobRender(BaseModel):
        width: int
        filetype: Literal['png', 'pdf', 'csv', 'xlsx']

    class Job(BaseModel):
        name: str
        page: JobPage
        render: JobRender
        crontab: str
        notifier: JobNotifier

    return [Job(**job_info) for job_info in jobs_info]


def register_jobs(scheduler: AsyncIOScheduler, grafana: Grafana, notifiers: dict):
    jobs = init_jobslist(list(notifiers.keys()))

    for job in jobs:
        try:
            if job.page.panel_uid:
                gfpage = grafana.dashboard(job.page.dashboard_uid).set_query(job.page.query).panel(
                    job.page.panel_uid)
            else:
                gfpage = grafana.dashboard(job.page.dashboard_uid).set_query(job.page.query)

            scheduler.add_job(
                func=render_and_send,
                trigger=CronTrigger.from_crontab(job.crontab),
                kwargs={
                    'gfpage': gfpage,
                    'public_url': PUBLIC_URL,
                    'width': job.render.width,
                    'filetype': job.render.filetype,
                    'notifier': notifiers.get(job.notifier.type),
                    'receiver': job.notifier.receiver
                }
            )
            logging.info(f"任务 {job.name} 已添加")
        except Exception as e:
            logging.debug(e)
            raise f"任务 {job} 添加失败，请检查配置是否正确"


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
    grafana = init_grafana()
    notifiers = init_notifier()

    register_jobs(scheduler, grafana, notifiers)
    register_clean_job(scheduler)

    scheduler.start()

    yield

    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)
app.mount("/files", StaticFiles(directory="files"), name="files")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
