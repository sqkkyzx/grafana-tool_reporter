from typing import List
from . import BaseNotifier, File
import httpx


class Gotify(BaseNotifier):
    def __init__(self, **kwargs):
        super().__init__()
        uri = kwargs.get('uri')
        self.uri = uri[:-1] if uri.endswith('/') else uri

    def send(self, file: File, receivers: List[str]):
        if file.filetype == 'png':
            text = f"""### {file.title}\n\n
{file.description}\n\n
![{file.title}]({file.fileurl})\n\n
> 页面源：[{file.viewurl}]({file.viewurl})"""
        else:
            text = f"""### {file.title}\n\n
{file.description}\n\n
[{file.fileurl}]({file.fileurl})\n\n
> 页面源：[{file.viewurl}]({file.viewurl})"""
        for receiver in receivers:
            httpx.post(
                self.uri,
                params={"token": receiver},
                json={
                    "message": text,
                    "priority": 5,
                    "title": file.title,
                    "extras": {
                        "client::display": {
                            "contentType": "text/plain"
                        }
                    }
                }
            )
