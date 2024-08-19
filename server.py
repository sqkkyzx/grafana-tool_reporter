from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from init import init_grafana, init_notifier, init_s3client, init_jobslist
from main import register_jobs, register_clean_job
from grafana import RenderJob

grafana_client = init_grafana()
enable_notifiers = init_notifier()
s3_client = init_s3client()


@asynccontextmanager
async def lifespan(myapp: FastAPI):
    scheduler = AsyncIOScheduler()

    # 初始化
    jobs = init_jobslist(grafana_client, enable_notifiers, s3_client)

    register_jobs(scheduler, jobs)
    register_clean_job(scheduler)

    scheduler.start()

    yield

    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)
app.mount("/files", StaticFiles(directory="files"), name="files")


@app.post("/grafana")
async def create_grafana_job(request: Request):
    job_info = await request.json()

    # 对可能没有传入的字段进行声明避免任务无法创建
    job_info['crontab_cfg'] = 'now'
    if job_info.get('notifier_cfg') is None:
        job_info['notifier_cfg'] = {'None': 'None'}
        job = RenderJob(
            grafana_client=grafana_client,
            enable_notifiers=enable_notifiers,
            s3client=s3_client,
            **job_info)
        file = job.render_file()
        return file.dict()
    else:
        job = RenderJob(
            grafana_client=grafana_client,
            enable_notifiers=enable_notifiers,
            s3client=s3_client,
            **job_info)
        job.notice()
        return None


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=False)
