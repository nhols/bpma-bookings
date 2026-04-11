from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from googleapiclient._apis.calendar.v3 import Event


class MockCalendarResource:
    def __init__(self, *args, **kwargs):
        pass

    def new_batch_http_request(self): ...
    def events(self):
        return self

    def insert(self, calendarId: str, body: Any = ...): ...
    def list(self, *args, **kwargs): ...
    def delete(self, *args, **kwargs): ...
