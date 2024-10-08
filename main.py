import logging
import os
import time
from typing import List

from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.background import BlockingScheduler

from grafana import RenderJob
from scripts import Script
from init import read_yaml, init_all


def register_jobs(scheduler: BlockingScheduler, jobs: List[RenderJob]):
    for job in jobs:
        try:
            scheduler.add_job(func=job.notice, trigger=CronTrigger.from_crontab(job.crontab_cfg),)
            logging.info(f"任务 {job.name} 已添加，执行计划：{job.crontab_cfg}")
        except Exception as e:
            logging.debug(e)
            raise f"任务 {job.name} 添加失败。"


def register_scripts(scheduler: BlockingScheduler, script_list: List[Script]):
    for script in script_list:
        try:
            scheduler.add_job(func=script.notice, trigger=CronTrigger.from_crontab(script.crontab_cfg),)
            logging.info(f"任务 {script.name} 已添加，执行计划：{script.crontab_cfg}")
        except Exception as e:
            logging.debug(e)
            raise f"任务 {script.name} 添加失败。"


def register_clean_job(scheduler: BlockingScheduler):
    expiry_days: int = read_yaml('config.yaml').get('files').get("expiry_days")

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


def main():
    scheduler = BlockingScheduler()

    # 初始化
    grafana_client, enable_notifiers, s3_client, job_list, script_list = init_all()

    # 注册任务
    if job_list:
        register_jobs(scheduler, job_list)
    if script_list:
        register_scripts(scheduler, script_list)

    register_clean_job(scheduler)

    # 启动调度器
    scheduler.start()

    try:
        # 这里可以添加你的代码，或者让调度器一直运行
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        # 关闭调度器
        scheduler.shutdown()
    finally:
        # 确保调度器关闭，无论退出是通过异常还是正常结束
        scheduler.shutdown()
        logging.info("调度器已关闭")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,  # 设置日志级别为INFO
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # 定义日志的格式
        datefmt='%Y-%m-%d %H:%M:%S',  # 定义时间的格式
    )
    main()
