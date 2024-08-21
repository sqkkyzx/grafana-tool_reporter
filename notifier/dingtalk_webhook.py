from typing import List
from .base import BaseNotifier, File
import httpx


class DingTalkWebhook(BaseNotifier):
    def __init__(self, **kwargs):
        super().__init__()
        uri = kwargs.get('uri')
        self.uri = uri[:-1] if uri.endswith('/') else uri

    def send(self, file: File, receivers: List[str]):
        if file.filetype == 'png':
            text = f"""### {file.title}\n\n\n
{file.description}\n\n\n
![{file.title}]({file.fileurl})\n\n\n
> 页面源：[{file.viewurl}]({file.viewurl})"""
        else:
            text = f"""### {file.title}\n\n
{file.description}\n\n
[{file.fileurl}]({file.fileurl})\n\n
> 页面源：[{file.viewurl}]({file.viewurl})"""
        for receiver in receivers:
            httpx.post(
                self.uri,
                params={"access_token": receiver},
                json={
                    "markdown": {
                        "title": file.title,
                        "text": text},
                    "msgtype": "markdown"
                }
            )
