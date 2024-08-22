from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request

from apscheduler.schedulers.background import BlockingScheduler

from init import init_all
from main import register_jobs, register_clean_job, register_scripts
from grafana import RenderJob


# 初始化
grafana_client, enable_notifiers, s3_client, job_list, script_list = init_all()


@asynccontextmanager
async def lifespan(myapp: FastAPI):
    scheduler = BlockingScheduler()

    # 注册任务
    if job_list:
        register_jobs(scheduler, job_list)
    if script_list:
        register_scripts(scheduler, script_list)

    register_clean_job(scheduler)

    scheduler.start()

    yield

    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)


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
