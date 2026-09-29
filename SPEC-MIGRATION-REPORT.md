# MCP 2026-07-28 migration

Lawmatics MCP targets protocol revision `2026-07-28`. The project requires
`mcp>=2.2,<3`; `uv.lock` resolves both `mcp` and its `mcp-types` companion to
`2.2.0`. The server uses `MCPServer` and runs over stdio. The SDK also provides
the in-process HTTP app used by protocol tests; the packaged entry point does
not enable HTTP.

The [specification delta](SPEC-DELTA-2026-07-28.md) maps the protocol changes
to this server. The [SDK migration guide](https://py.sdk.modelcontextprotocol.io/migration/)
describes the SDK API changes.

## Implemented behavior

- The server registers 36 tools, three resources, and three prompts. Each list
  call makes at most one Lawmatics request. Paginated tools require `page >= 1`;
  the seven standard list endpoints expose their supported sorting fields.
- SDK dispatch handles per-request protocol metadata, `server/discover`,
  `resultType`, cache hints, structured tool results, and modern error codes.
  Tests exercise these through an in-process HTTP transport and also check
  modern and legacy client negotiation. Production remains stdio.
- SDK-managed list-change and resource-subscription capabilities are declared;
  the application adds no event publisher. No unused capability extension is
  advertised.
- Validation and API rejection paths log fixed reasons or numeric status and
  method fields. API errors and OAuth setup failures omit vendor response
  bodies. Lawmatics credentials remain file or environment based.

## Reproduce the offline checks

Use a clean environment without real Lawmatics credentials. The pytest fixture
sets fake values and redirects credential storage to a temporary directory.
The suite mocks vendor HTTP; protocol tests use an in-process transport.

```bash
uv run --offline --locked --with pytest pytest -q
uv run --offline --locked python tests/spec_check.py --mcp-only
uv lock --check --offline
```

Ruff is configured for Python 3.10 in `pyproject.toml`. With Ruff available
locally, run `ruff check .`. The protocol guard checks the installed SDK's
revision constant; the separate protocol tests exercise request and response
behavior. Live Lawmatics API behavior and deployment are outside these checks.

## Error behavior

Tool calls return actionable client errors for missing credentials, rejected
authorization, rate limits, invalid arguments, and classified API failures.
Unexpected failures return a fixed masked message. Error responses omit vendor
response bodies, exception details, URLs, and rejected argument values. Read
timeouts and connection failures can be retried; for writes the outcome is
unknown, so callers should check whether the change completed before retrying.
Resource read failures raise safe resource errors without exposing the underlying
exception.
