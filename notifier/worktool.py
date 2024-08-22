from typing import List
from . import BaseNotifier, File
import httpx


class Worktool(BaseNotifier):
    def __init__(self, **kwargs):
        super().__init__()
        uri = kwargs.get('uri')
        self.uri = uri[:-1] if uri.endswith('/') else uri
        self.robotid: str = kwargs.get('robot_id')

    def send(self, file: File, receivers: List[str]):
        action_list = []
        for receiver in receivers:
            filetype = 'image' if file.filetype == 'png' else '*'
            hexstring = file.title.encode('utf-8').hex()
            action = {
                "type": 218,
                "titleList": receiver,
                "objectName": F"{hexstring}.{file.filetype}",
                "fileUrl": file.filepath,
                "fileType": filetype,
                "extraText": f"#{file.title}\n{file.description}"
            }
            action_list.append(action)

        httpx.post(
                self.uri,
                params={"robotId": self.robotid},
                json={
                    "socketType": 2,
                    "list": action_list
                }
            )
