from dataclasses import dataclass

DEFAULT_NAME = "World"


@dataclass(frozen=True)
class Greeting:
    message: str


def greeting_for(name: str | None) -> Greeting:
    return Greeting(message=f"Hello, {name or DEFAULT_NAME}!")
