from dataclasses import dataclass, field


@dataclass
class Job:
    id: str
    title: str
    company: str
    location: str
    url: str
    description: str
    source: str
    remote: bool
    posted: str = ""
    score: int = 0
    reason: str = ""
    extra: dict = field(default_factory=dict)
