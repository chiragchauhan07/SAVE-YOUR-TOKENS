"""One module per generated Knowledge Base file.

Each module exposes a single ``render()`` function: ``Project`` in, a
``Document`` out. No module here reads a file, walks a directory, or parses
anything — every fact comes from the ``Project`` object already handed to
it.
"""
