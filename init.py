import os
import shutil
from typing import Dict, List

import yaml
import logging
from grafana import Grafana, RenderJob
import notifier
from notifier import BaseNotifier


def read_yaml(cfgfile):
    filepath = f'config/{cfgfile}'
    example_filepath = f'config.example/{cfgfile}'

    if not os.path.exists(filepath):
        if os.path.exists(example_filepath):
            shutil.copy(example_filepath, filepath)
            logging.warning(f"配置未设置。文件 {cfgfile} 已从 config.example 复制。请修改此文件以符合您的配置。")
            raise Exception(f"配置未设置。文件 {cfgfile} 已从 config.example 复制。请修改此文件以符合您的配置。")
        else:
            logging.error(f"{cfgfile} 及其示例在预期目录中均不存在。")
            raise FileNotFoundError(f"{cfgfile} 及其示例在预期目录中均不存在。")

    with open(filepath, 'r', encoding='utf-8') as file:
        try:
            # 加载 YAML 内容
            data = yaml.safe_load(file)

            # 检查文件是否与示例相同
            if os.path.exists(example_filepath):
                with open(example_filepath, 'r', encoding='utf-8') as example_file:
                    example_data = yaml.safe_load(example_file)
                    if data == example_data:
                        logging.warning(f"配置未设置。文件 {cfgfile} 与示例相同。请修改此文件以符合您的配置。")
                        raise Exception(f"配置未设置。文件 {cfgfile} 与示例相同。请修改此文件以符合您的配置。")

            return data

        except yaml.YAMLError as exc:
            logging.error(f"YAML 文件错误: {exc}。无法加载 {filepath}，请检查 YAML 语法是否有误。")
            raise Exception(f"无法加载 {filepath}，请检查 YAML 语法是否有误。")


def init_grafana() -> Grafana:
    try:
        grafana_config: dict = read_yaml('config.yaml').get('grafana', {})

        env_public_url = os.getenv('GRAFANA_PUBLIC_URL')
        env_token = os.getenv('GRAFANA_TOKEN')

        if env_public_url and env_token:
            grafana_config['public_url'] = env_public_url
            grafana_config['token'] = env_token

        return Grafana(**grafana_config)

    except Exception as e:
        raise e


def init_notifier() -> Dict[str, BaseNotifier]:
    notifiers_config: dict = read_yaml('notifier.yaml')
    provided_notifiers: list[str] = list(notifiers_config.keys())

    enabled_notifiers: Dict[str, BaseNotifier] = {}

    for notifier_type in provided_notifiers:
        notifier_class = getattr(notifier, notifier_type, None)
        if notifier_class:
            enabled_notifiers[notifier_type] = notifier_class(**notifiers_config.get(notifier_type))
        else:
            logging.warning(f'提供的通知器 [{notifier_type}] 不受支持。')

    if not enabled_notifiers:
        logging.error('配置中没有启用任何通知器。')
        raise Exception('没有提供任何通知器。')

    return enabled_notifiers


def init_jobslist(grafana: Grafana, enable_notifiers: Dict[str, BaseNotifier], public_url: str) -> List[RenderJob]:
    jobs_info = read_yaml('job.yaml').get('jobs')
    return [
        RenderJob(
            grafana_client=grafana,
            enable_notifiers=enable_notifiers,
            public_url=public_url,
            **job_info
        ) for job_info in jobs_info
    ]
