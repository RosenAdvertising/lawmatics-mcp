# MCP specification delta: 2025-11-25 to 2026-07-28

This note maps the [2026-07-28 specification changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
to Lawmatics MCP. The project requires `mcp>=2.2,<3`; `uv.lock` resolves
`mcp==2.2.0` and `mcp-types==2.2.0`. The packaged server runs over stdio.
Protocol tests additionally exercise the SDK's in-process HTTP app.

| Protocol change | Lawmatics mapping |
| --- | --- |
| Modern requests carry protocol version and capabilities per request; `initialize` is absent from that flow. | SDK dispatch handles modern requests and legacy negotiation. Tests exercise both client modes. |
| `server/discover` is required. | Discovery tests assert supported version, server identity, capabilities, private cache hints, and no session header. |
| Results carry `resultType`. | Discovery, list, resource-read, and tool-call tests assert `complete`. |
| HTTP POST routing uses `Mcp-Method` and `Mcp-Name` for named operations. | In-process HTTP tests assert routing-header validation. The packaged entry point still uses stdio; no tool uses `x-mcp-header`. |
| `subscriptions/listen` replaces older resource subscription routes. | The SDK declares list-change and resource-subscription capabilities. This application has no custom publisher or event bus. |
| Capabilities may contain `extensions`. | Discovery tests assert that no unused extension is advertised. |
| List/read responses carry `ttlMs` and `cacheScope`. | Tests assert the SDK's private, zero-TTL defaults for relevant results. |
| `tools/list` order should be deterministic. | Repeated listings are compared in registration order. |
| Tool schemas allow JSON Schema 2020-12; structured content accepts any JSON value. | SDK-generated object schemas and structured results are tested. Paginated tools declare a page minimum of one. |
| Unknown resources use Invalid Params `-32602`. | A missing Lawmatics resource test asserts the code. |
| Modern errors include header mismatch `-32020`, unsupported version `-32022`, and unknown method `-32601`. | In-process HTTP tests assert these reachable cases. |

## Scope and caveats

- The application has no server-initiated sampling, roots, elicitation, protocol
  task handler, MCP authorization server, dynamic client registration, trace
  integration, event replay store, or legacy HTTP+SSE entry point. Lawmatics
  OAuth setup is separate from MCP transport authorization.
- The application does not publish subscription events. Capability declarations
  and wire behavior are handled by the SDK.
- Lawmatics list tools issue one vendor request per call. Standard list
  endpoints expose supported sort and filter arguments; specialized endpoints
  retain their narrower documented parameters.
- Offline tests use fake credentials, mocked vendor requests, and an
  in-process protocol transport. They do not verify a live Lawmatics account.

Run the full suite, protocol guard, and lock check with the commands in the
[migration report](SPEC-MIGRATION-REPORT.md).
