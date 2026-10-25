from backend.domain.greeting import Greeting, greeting_for


def get_greeting(name: str | None = None) -> Greeting:
    return greeting_for(name)
