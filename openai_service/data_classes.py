from dataclasses import dataclass

@dataclass
class MessageDTO:
    text: str
    author_id: int

@dataclass
class Result:
    result: str