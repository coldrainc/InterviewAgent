# API regression

Fast unit and route tests remain in `backend/tests`. The production-style HTTP
acceptance runner remains in `scripts/release_acceptance` and can be invoked
against an explicitly isolated stack:

```bash
backend/.venv/bin/python -m scripts.release_acceptance.main \
  --base-url http://127.0.0.1:18080/api \
  --state-file /tmp/interview-agent-acceptance.json \
  --phase full \
  --confirm-isolated
```

Run the `persistence` phase after restarting the stack, followed by `logout`.
The confirmation flag is mandatory because the suite creates and deletes test
accounts and resources.
