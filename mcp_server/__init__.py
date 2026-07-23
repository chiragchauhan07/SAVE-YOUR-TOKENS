"""Phase 5: expose the analysis engine and Knowledge Base generator through
the Model Context Protocol.

This package is an integration layer, not another analysis phase — it
contains almost no logic of its own:

- ``handlers.py`` calls ``analyzer.analyze_repository()`` and
  ``generator.generate_knowledge_base()`` directly. No re-scanning,
  re-parsing, or duplicated business logic.
- ``tools.py`` is the only module that imports the MCP SDK; every tool
  catches its own exceptions and returns a safe, structured response.
- ``server.py`` is the stdio entry point.

Running the MCP server or the CLI against the same repository produces
identical results — both call the same underlying engine and generator
functions, and neither changes anything about repository intelligence.
"""
