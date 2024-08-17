import logging

import schedule
import os
import time
from grafana import Grafana


def add_jobs():
    jobs = []
    for job in jobs:
        try:
            pass
            logging.info(f"任务 {job} 已添加")
        except Exception as e:
            logging.debug(e)
            raise f"任务 {job} 添加失败，请检查配置是否正确"


if __name__ == "__main__":
    GRAFANA_DOMIN = os.getenv('GRAFANA_DOMIN')
    GRAFANA_TLS = os.getenv('GRAFANA_TLS').lower() == 'true'
    GRAFANA_TOKEN = os.getenv('GRAFANA_TOKEN')
    grafana = Grafana(domain=GRAFANA_DOMIN, tls=GRAFANA_TLS, token=GRAFANA_TOKEN)

    add_jobs()

    while True:
        schedule.run_pending()
        time.sleep(1)
