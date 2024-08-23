from typing import List
from . import BaseNotifier, File
import httpx


class DingTalkWebhook(BaseNotifier):
    def __init__(self, **kwargs):
        super().__init__()
        uri = kwargs.get('uri')
        self.uri = uri[:-1] if uri.endswith('/') else uri

    def send(self, file: File, receivers: List[str]):
        if file.filetype == 'png':
            text = f"""### {file.title}\n\n
![{file.title}]({file.fileurl})\n\n
> 页面：[{file.viewurl}]({file.viewurl})\n
> 描述: {file.description}"""
        else:
            text = f"""### {file.title}\n\n
[{file.fileurl}]({file.fileurl})\n\n
> 页面：[{file.viewurl}]({file.viewurl})\n
> 描述: {file.description}"""
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
