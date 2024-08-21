from abc import ABC, abstractmethod
from typing import List


class File(ABC):
    title: str
    filetype: str
    filepath: str
    fileurl: str
    viewurl: str
    description: str


class BaseNotifier(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def send(self, file: File, receiver: List[str]):
        pass
