"""Fixture data layer. Deliberately trivial and in-memory."""

from dataclasses import dataclass

_NOTES: dict[int, "Note"] = {}


@dataclass
class Note:
    id: int
    title: str
    body: str

    def as_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "body": self.body}

    @classmethod
    def all(cls) -> list["Note"]:
        return list(_NOTES.values())

    @classmethod
    def get(cls, note_id: int) -> "Note":
        return _NOTES[note_id]
