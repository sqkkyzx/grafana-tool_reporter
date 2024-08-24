import json
import os
import time
from typing import List
from . import BaseNotifier, File
import httpx


class DingTalkApp(BaseNotifier):
    def __init__(self, **kwargs):
        super().__init__()
        self.app_key = kwargs.get('app_key')
        self.app_secret = kwargs.get('app_secret')
        self.robot_code = kwargs.get('robot_code')
        self.coolapp_code = kwargs.get('coolapp_code')
        self.access_token, self.access_expire = None, 0

    def _get_access_token(self):
        if self.access_expire > int(time.time()) and self.access_token:
            return self
        access = httpx.post(
            url='https://api.dingtalk.com/v1.0/oauth2/accessToken',
            json={"appKey": self.app_key, "appSecret": self.app_secret}
        ).json()
        token = access.get('accessToken')
        expire = int(time.time()) + access.get('expireIn', 0)
        if token:
            self.access_token = token
            self.access_expire = expire
        else:
            self.access_token = None
            self.access_expire = 0
        return self

    def _upload(self, filepath):
        self._get_access_token()
        file_extension = os.path.splitext(filepath)[1].lower()
        media_type_mapping = {
            '.jpg': 'image',
            '.jpeg': 'image',
            '.png': 'image',
            '.gif': 'image',
            '.bmp': 'image',
            '.amr': 'voice',
            '.mp3': 'voice',
            '.wav': 'voice',
            '.mp4': 'video',
            '.doc': 'file',
            '.docx': 'file',
            '.xls': 'file',
            '.xlsx': 'file',
            '.ppt': 'file',
            '.pptx': 'file',
            '.zip': 'file',
            '.pdf': 'file',
            '.rar': 'file'
        }
        media_type = media_type_mapping.get(file_extension, 'file')
        with open(filepath, 'rb') as file:
            files = {'media': file, 'type': media_type}
            res = httpx.post(
                url='https://oapi.dingtalk.com/media/upload',
                params={'access_token': self.access_token},
                files=files).json()
        if res.get('errmsg') == 'ok':
            return res.get('media_id')
        else:
            return None

    def send(self, file: File, receivers: List[str]):
        self._get_access_token()
        media_id = self._upload(file.filepath)
        if not media_id:
            return
        param = {
            "mediaId": media_id,
            "fileName": str(file.filepath).split('/')[-1],
            "fileType": file.filetype,
        }
        for receiver in receivers:
            payload = {
                "msgParam": json.dumps(param, ensure_ascii=False),
                "msgKey": "sampleFile",
                "openConversationId": receiver
            }
            if self.robot_code:
                payload['robotCode'] = self.robot_code
            if self.coolapp_code:
                payload['coolAppCode'] = self.coolapp_code
            httpx.post('https://api.dingtalk.com/v1.0/robot/groupMessages/send', json=payload)
