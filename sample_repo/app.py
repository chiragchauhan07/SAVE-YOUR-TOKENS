"""Fixture Flask application. Not part of the Blueprint package."""

from flask import Flask, jsonify

from models import Note
from config import SETTINGS

app = Flask(__name__)


@app.route("/health")
def health():
    return jsonify(status="ok")


@app.route("/notes", methods=["GET"])
def list_notes():
    return jsonify([note.as_dict() for note in Note.all()])


@app.route("/notes/<int:note_id>", methods=["GET"])
def get_note(note_id):
    return jsonify(Note.get(note_id).as_dict())


if __name__ == "__main__":
    app.run(debug=SETTINGS["debug"])
