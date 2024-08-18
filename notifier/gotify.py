import httpx


class Gotify:
    def __init__(self, **kwargs):
        uri = kwargs.get('uri')
        self.uri = uri[:-1] if uri.endswith('/') else uri

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
