import asyncio
import logging
from contextlib import asynccontextmanager
import schedule

import uvicorn
import yaml

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from grafana import Grafana
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


def init_grafana():
    grafana_config: dict = read_yaml('config/config.yaml').get('grafana')
    return Grafana(**grafana_config)


def init_notifier():
    notifier_config: dict = read_yaml('config/notifier.yaml')
    return {
        'worktool': notifier.Worktool(**notifier_config.get('worktool')),
        'gotify': notifier.Gotify(**notifier_config.get('gotify')),
        'dintalk_webhook': notifier.DingTalkWebhook(**notifier_config.get('dintalk_webhook'))
    }


def init_jobs():
    jobs = []
    for job in jobs:
        try:
            pass
            logging.info(f"任务 {job} 已添加")
        except Exception as e:
            logging.debug(e)
            raise f"任务 {job} 添加失败，请检查配置是否正确"


@asynccontextmanager
async def lifespan(myapp: FastAPI):
    # 启动调度任务的异步任务
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    grafana = init_grafana()
    notifiers = init_notifier()
    init_jobs()

    async def run_schedule():

        while not stop_event.is_set():
            try:
                schedule.run_pending()
            except Exception as e:
                logging.error(f'Task field with {e}')
            await asyncio.sleep(1)

    schedule_task = loop.create_task(run_schedule())

    yield
    # 停止调度任务
    stop_event.set()
    await schedule_task


app = FastAPI(lifespan=lifespan)
app.mount("/files", StaticFiles(directory="files"), name="files")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
