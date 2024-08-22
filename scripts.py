import json
import logging
import re
import subprocess
from typing import List, Dict, Tuple

from notifier import BaseNotifier, File
from s3 import S3Client


class Script:
    def __init__(self, enable_notifiers, s3client, **kwargs):
        self.enable_notifiers: Dict[str, BaseNotifier] = enable_notifiers
        self.s3client: S3Client = s3client

        self.name: str = kwargs.get('name', 'UnnamedJob')

        self.scriptfile_cfg: str = self._get_must_value(kwargs, 'page')
        self.crontab_cfg: str = self._get_must_value(kwargs, 'crontab')
        self.notifier_cfg: dict = self._get_must_value(kwargs, 'notifier')

        # 没有使用API请求时，必循
        if self.notifier_cfg != {'None': 'None'}:
            notifier: Tuple[BaseNotifier, List[str]] = self._get_notifier()
            self.notifier: BaseNotifier = notifier[0]
            self.receiver: List[str] = notifier[1]
        else:
            self.notifier = None
            self.receiver = None

        self.scriptfile_path = 'custom_scripts/' + self.scriptfile_cfg

    def _get_must_value(self, dictionary: dict, key: str):
        value = dictionary.get(key)
        if value:
            return value
        else:
            logging.error(f'任务 {self.name} 的配置中缺少字段： {key}')
            raise Exception(f'任务 {self.name} 的配置中缺少字段： {key}')

    def _get_notifier(self) -> Tuple[BaseNotifier, List[str]]:
        receiver: List[str] = self._get_must_value(self.notifier_cfg, 'receiver')
        name: str = self._get_must_value(self.notifier_cfg, 'type')
        notifiers: BaseNotifier = self.enable_notifiers.get(name)
        if notifiers and receiver:
            return notifiers, receiver
        elif receiver is None or receiver == [None]:
            logging.error(f'任务 {self.name} 没有设置通知接收人。')
            raise Exception(f'任务 {self.name} 没有设置通知接收人。')
        else:
            logging.error(f'不支持任务 {self.name} 的配置中设置的通知器 {name} 。')
            raise Exception(f'不支持任务 {self.name} 的配置中设置的通知器 {name} 。')

    def notice(self):
        # 使用subprocess.run来执行脚本
        result = subprocess.run(["python", self.scriptfile_path], capture_output=True, text=True)
        # 脚本已经运行完成，此时可以检查返回码
        if result.returncode == 0 and self.receiver:
            logging.info("脚本执行成功")
            # 从标准输出中提取包含 'filepath' 字段的 JSON 字符串
            file_infoextracted_json = self.extract_json_with_filepath(result.stdout)
            if file_infoextracted_json:
                title = file_infoextracted_json.get('title', '')
                filepath = file_infoextracted_json.get('filepath')
                filetype = file_infoextracted_json.get('filetype')
                fileurl = file_infoextracted_json.get('fileurl')
                viewurl = file_infoextracted_json.get('viewurl', '')
                description = file_infoextracted_json.get('description', '')
                if not filetype and filepath:
                    filetype = filepath.split('.')[-1]
                if not fileurl and filepath:
                    fileurl = self.s3client.upload(filepath)

                logging.info(f"解析到输出文件为 {filepath}")
                file: File = File(title=title, filetype=filetype, filepath=filepath, fileurl=fileurl, viewurl=viewurl, description=description)
                self.notifier.send(file, self.receiver)
            else:
                logging.error(f"任务 {self.name} 无法解析文件路径，无法发送通知。")
        else:
            logging.error(f"任务 {self.name} 页面渲染失败，无法发送通知。")

    @staticmethod
    def extract_json_with_filepath(stdout):
        """
        从标准输出中提取包含 'filepath' 字段的 JSON 字符串并返回其字典表示。
        如果找不到匹配的 JSON 或解析失败，则返回 None。

        :param stdout: 标准输出字符串
        :return: 包含 'filepath' 字段的字典，或者 None
        """
        # 使用正则表达式提取包含 'filepath' 字段的 JSON 字符串
        re_exp = r'\{.*?"filepath".*?\}'
        pattern = re.compile(re_exp)
        matches = pattern.findall(stdout)

        # 尝试解析每一个匹配的 JSON 字符串
        for match in matches:
            try:
                json_data = json.loads(match)
                # 检查是否包含 'filepath' 字段
                if 'filepath' in json_data:
                    return json_data
            except json.JSONDecodeError:
                continue

        # 如果没有找到匹配的 JSON 或解析失败，返回 None
        return None
