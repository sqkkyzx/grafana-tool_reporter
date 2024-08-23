import os
import shutil
from typing import Dict, List

import yaml
import logging

from ai import api_key
from grafana import Grafana, RenderJob
from s3 import S3Client
import notifier
from notifier import BaseNotifier
from scripts import Script
from openai import OpenAI


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


def init_s3client() -> S3Client:
    try:
        # 读取配置文件
        s3_config: dict = read_yaml('config.yaml').get('s3', {})

        # 从环境变量中获取S3配置，优先使用环境变量
        env_region = os.getenv('S3_REGION')
        env_bucket = os.getenv('S3_BUCKET')
        env_endpoint_url = os.getenv('S3_ENDPOINT_URL')
        env_public_url = os.getenv('S3_PUBLIC_URL')
        env_access_key_id = os.getenv('S3_ACCESS_KEY_ID')
        env_secret_access_key = os.getenv('S3_SECRET_ACCESS_KEY')
        env_addressing_style = os.getenv('S3_ADDRESSING_STYLE')

        # 更新配置字典
        if env_region:
            s3_config['region'] = env_region
        if env_bucket:
            s3_config['bucket'] = env_bucket
        if env_endpoint_url:
            s3_config['endpoint_url'] = env_endpoint_url
        if env_public_url:
            s3_config['public_url'] = env_public_url
        if env_access_key_id:
            s3_config['access_key_id'] = env_access_key_id
        if env_secret_access_key:
            s3_config['secret_access_key'] = env_secret_access_key
        if env_addressing_style:
            s3_config['addressing_style'] = env_addressing_style

        # 创建并返回S3客户端
        return S3Client(**s3_config)

    except Exception as e:
        raise e


def init_openai() -> OpenAI | None:
    try:
        # 读取配置文件
        openai_config: dict = read_yaml('config.yaml').get('openai', {})

        # 从环境变量中获取S3配置，优先使用环境变量
        env_api_key = os.getenv('OPENAI_API_KEY')
        env_base_url = os.getenv('OPENAI_BASE_URL')

        # 更新配置字典
        if env_api_key:
            openai_config['api_key'] = env_api_key
        if env_base_url:
            openai_config['base_url'] = env_base_url

        # 创建并返回S3客户端
        if openai_config.get('base_url'):
            return OpenAI(**openai_config)
        else:
            return OpenAI(api_key=openai_config.get('api_key'))

    except Exception as e:
        logging.debug(e)
        logging.warning('未配置OPENAI')
        return None


def init_jobslist(grafana: Grafana, enable_notifiers: Dict[str, BaseNotifier], s3client: S3Client, openai: OpenAI) -> List[RenderJob]:
    jobs_info = read_yaml('job.yaml').get('grafana')
    if jobs_info:
        return [
            RenderJob(
                grafana_client=grafana,
                enable_notifiers=enable_notifiers,
                s3client=s3client,
                openai=openai,
                **job_info
            ) for job_info in jobs_info
        ]
    else:
        return []


def init_scriptlist(enable_notifiers: Dict[str, BaseNotifier], s3client: S3Client) -> List[Script]:
    scripts_info = read_yaml('job.yaml').get('script')
    if scripts_info:
        return [
            Script(
                enable_notifiers=enable_notifiers,
                s3client=s3client,
                **script_info
            ) for script_info in scripts_info
        ]
    else:
        return []


def init_all():
    grafana_client = init_grafana()
    enable_notifiers = init_notifier()
    s3_client = init_s3client()
    openai_client = init_openai()
    job_list = init_jobslist(grafana_client, enable_notifiers, s3_client, openai_client)
    script_list = init_scriptlist(enable_notifiers, s3_client)
    return grafana_client, enable_notifiers, s3_client, job_list, script_list
