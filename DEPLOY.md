# Using kazen-event-schema in a service

`kazen-event-schema` is a library; there is nothing to deploy on its own.
Install it in any service that produces or consumes `KazenEvent`s:

```bash
python -m pip install "kazen-event-schema>=0.6,<0.7"
```

It needs no environment variables. Verify an install with:

```bash
python -c "from kazen_event_schema import KazenEvent; print(KazenEvent.__name__)"
```

## Develop

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest   # enforces at least 80% coverage
```

Releases follow [RELEASING.md](RELEASING.md).
