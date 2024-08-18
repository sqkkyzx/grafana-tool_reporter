import httpx


class Gotify:
    def __init__(self, **kwargs):
        self.uri = kwargs.get('uri')

    def send(self, receivers, title, filepath):
        for receiver in receivers:
            httpx.post(
                self.uri,
                params={"access_token": receiver},
                json={
                    "markdown": {"title": title, "text": filepath},
                    "msgtype": "markdown"
                }
            )
