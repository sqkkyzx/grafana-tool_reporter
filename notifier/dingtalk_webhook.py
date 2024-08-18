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
            text = f"""
            ### {file.title}
            {file.slug}
            ![{file.title}]({file.fileurl})
            ---
            [{file.viewurl}]({file.viewurl})
            """
        else:
            text = f"""
            ### {file.title}
            {file.slug}
            [{file.fileurl}]({file.fileurl})
            ---
            [{file.viewurl}]({file.viewurl})
            """
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
