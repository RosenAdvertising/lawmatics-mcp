# MCP specification delta: 2025-11-25 to 2026-07-28

Research date: 2026-08-09. Sources are limited to the official MCP
specification and official MCP Python SDK documentation.

Integration note (2026-09-28): The baseline below describes the original spec
branch. The merged v2 candidate retains main's `mcp>=1.0.0` requirement and
main's `uv.lock` resolution of MCP SDK `2.0.0`.

## Current target and migration release

The original spec-branch baseline targeted MCP `2025-11-25`:

- `pyproject.toml` declares the broad dependency `mcp>=1.0.0`, while
  `uv.lock` resolves MCP Python SDK `1.28.1`.
- `lawmatics_mcp/server.py` constructs the v1 `FastMCP` class and does not
  override protocol negotiation. The installed SDK reports
  `LATEST_PROTOCOL_VERSION == "2025-11-25"`.
- The packaged entry point calls `mcp.run()` and therefore serves stdio only.
  Tests inspect the high-level registries but do not pin or exercise a wire
  protocol revision.

The official changelog says `2026-07-28` follows `2025-11-25`
([spec changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)).
MCP Python SDK `2.0.0` is the exact stable migration release: its release notes
say it supports `2026-07-28` and serves every earlier revision from the same
server
([SDK v2.0.0 release notes](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0)).
The implementation changes below follow the
[official v1-to-v2 migration guide](https://py.sdk.modelcontextprotocol.io/migration/).

Verdicts mean:

- **AFFECTS-US**: this server exposes or relies on the changed surface. The SDK
  may implement the wire behavior, but the migration must still pin, configure,
  or test it.
- **NOT-APPLICABLE**: the feature or direction is not implemented here and will
  not be added only because the new revision permits it.

## Protocol negotiation and lifecycle

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| Protocol-level sessions and `Mcp-Session-Id` are removed. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | The production entry point is stdio-only and the application keeps no MCP session state. The modern raw-wire regression will nevertheless prove the SDK's HTTP app does not introduce a session-header dependency. |
| Modern requests remove `initialize` / `notifications/initialized` and carry version/capability metadata on each request; version mismatches use `UnsupportedProtocolVersionError`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | Stdio is the shipped transport. SDK v2's dual-era dispatcher must accept modern self-describing requests while retaining legacy negotiation. |
| Servers must implement `server/discover`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | Every modern server must advertise its versions, identity, and actual capabilities. |
| All results require `resultType`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | Lawmatics returns tool, resource, prompt, and discovery results. Wire tests must prove ordinary results serialize as `complete`. |
| Multi Round-Trip Requests replace server-initiated requests. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | No tool, resource, or prompt uses sampling, roots, elicitation, or another server-to-client request. |
| `ping`, `logging/setLevel`, and `notifications/roots/list_changed` are removed; protocol logging becomes per-request opt-in. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | The server implements none of these methods and has no MCP logging-notification integration. Application logging remains ordinary Python logging. |

## Transports and notifications

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| Streamable HTTP POST requires `Mcp-Method` and, for named operations, `Mcp-Name`; `x-mcp-header` maps selected tool parameters to headers. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | The high-level server exposes an SDK-owned Streamable HTTP app surface even though the packaged entry point uses stdio. Offline raw-wire tests will verify header validation without enabling a new production transport. No tool opts into `x-mcp-header`. |
| HTTP GET plus `resources/subscribe` / `resources/unsubscribe` are replaced by `subscriptions/listen`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | The high-level server exposes SDK-managed list-change/resource-subscription declarations. SDK v2 maps those declarations to the modern transport; this migration adds no publisher or custom event bus. |
| SSE resumability/redelivery is removed. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | The server configures no event store and relies on no replay behavior. |
| Legacy HTTP+SSE is formally deprecated. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | The entry point serves stdio and does not expose the legacy HTTP+SSE transport. |

## Capabilities and extensions

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| Client and server capabilities gain `extensions`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | `server/discover` exposes the capability shape. No unused extension should be advertised. |
| Experimental tasks move to `io.modelcontextprotocol/tasks`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | There are no protocol-task handlers or task-augmented MCP tools; SDK v2.0.0 does not implement the extension. Lawmatics CRM task tools are ordinary MCP tools, not the protocol feature. |
| Roots, Sampling, and Logging are deprecated. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | None is declared or used. |
| Sampling `includeContext` values `thisServer` and `allServers` are deprecated. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | Sampling is not used. |

## Tools, resources, prompts, and cache semantics

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| List/read results require `ttlMs` and `cacheScope`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | The server exposes 36 tools, three prompts, three resources, and resource reads. Tests will assert the SDK's conservative private zero-TTL defaults. |
| `tools/list` should be deterministic. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | Registration order is stable and repeated discovery will be compared exactly. |
| Tool schemas accept JSON Schema 2020-12 and structured content may be any JSON value. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | Decorators generate all tool schemas. SDK v2 owns the widened model support; regression tests will inspect valid object schemas without adding optional schema features. |
| Resource-not-found changes to JSON-RPC Invalid Params `-32602`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | The server exposes three static resources, so an unknown URI must produce the new code. |
| URL elicitation removes its completion notification and `elicitationId`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | The server performs no elicitation. |
| Generated schema numeric bounds/defaults are numbers rather than integers. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#other-schema-changes) | **NOT-APPLICABLE** | The repository neither vendors the protocol schema nor directly validates against that numeric meta-schema; SDK v2 absorbs the correction. |

## Authorization and security

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| Authorization responses should include RFC 9207 `iss`, which clients validate. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | This server does not implement MCP transport authorization. Its separate Lawmatics OAuth setup is downstream vendor authorization, outside MCP client authorization. |
| Dynamic Client Registration clients must send `application_type`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | The code does not dynamically register an MCP client. |
| Persisted MCP client credentials must be keyed to their authorization-server issuer. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | No MCP client registration credentials are stored. The Lawmatics token is vendor-specific and already scoped to its fixed API. |
| Dynamic Client Registration is deprecated in favor of Client ID Metadata Documents. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | The server neither hosts DCR nor acts as a dynamically registered MCP client. |

## Errors, metadata, and observability

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| MCP reserves `-32020..-32099`; header mismatch, missing capability, and unsupported version become `-32020`, `-32021`, and `-32022`; unknown methods use `-32601`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | SDK v2 must return the modern codes. Offline wire tests will cover the reachable cases without manufacturing a feature requiring optional client capabilities. |
| `_meta` formally carries W3C trace context. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | The server has no protocol `_meta` tracing integration; this migration will not add an observability feature. |

Governance and SEP workflow changes are omitted because they impose no runtime
or server implementation requirement. The feature lifecycle is respected by
not adding deprecated Roots, Sampling, Logging, HTTP+SSE, or DCR support.
