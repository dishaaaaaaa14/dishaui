# Ingestion fixtures

These files are small synthetic teaching documents used by the B5 ingestion
tests. They are generated locally and contain no third-party content.

- `sample.pdf`: two pages covering Newton's second law, a formula, and a worked example.
- `sample.pptx`: three slides with a title, bullet lists, a table, and a speaker note.

Regenerate them with:

```powershell
python tools/make_ingest_fixtures.py
```

The fixtures are CC0-1.0. The PDF uses Matplotlib's PDF backend and the PPTX uses
`python-pptx`; both are development-only dependencies of the fixture generator.
