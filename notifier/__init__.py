from .dingtalk_webhook import DingTalkWebhook
from .gotify import Gotify
from .worktool import Worktool
from abc import ABC, abstractmethod
from typing import List


__all__ = [
    'BaseNotifier', 'File',
    'DingTalkWebhook',
    'Gotify',
    'Worktool'
]


class File:
    def __init__(self, filetype, filepath, title='', fileurl='', viewurl='', description=''):
        self.title = title
        self.filetype = filetype
        self.filepath = filepath
        self.fileurl = fileurl
        self.viewurl = viewurl
        self.description = description

    def dict(self):
        return {
            'title': self.title,
            'filetype': self.filetype,
            'filepath': self.filepath,
            'fileurl': self.fileurl,
            'viewurl': self.viewurl,
            'description': self.description
        }


class BaseNotifier(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def send(self, file: File, receiver: List[str]):
        pass
