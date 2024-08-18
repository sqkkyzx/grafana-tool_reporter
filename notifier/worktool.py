import httpx


class Worktool:
    def __init__(self, **kwargs):
        uri = kwargs.get('uri')
        self.uri = uri[:-1] if uri.endswith('/') else uri
        self.robotid: str = kwargs.get('robot_id')

    def send(self, receivers, title, filepath):
        action_list = []
        for receiver in receivers:
            file_type = 'image' if '.png' in filepath else '*'
            action = {
                "type": 218,
                "titleList": receiver,
                "objectName": title,
                "fileUrl": filepath,
                "fileType": file_type,
                "extraText": title
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
