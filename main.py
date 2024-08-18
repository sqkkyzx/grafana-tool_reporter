import logging
from multiprocessing.pool import worker

import schedule
import time
import yaml

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


if __name__ == "__main__":
    grafana = init_grafana()
    notifiers = init_notifier()
    init_jobs()
    while True:
        schedule.run_pending()
        time.sleep(1)
