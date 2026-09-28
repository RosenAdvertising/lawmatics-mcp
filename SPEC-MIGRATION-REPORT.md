# MCP 2026-07-28 migration report

## Result

The original spec branch migrated `lawmatics-mcp` to MCP `2026-07-28` from
`2025-11-25` and pinned the Python SDK to `mcp==2.0.0`. The merged v2 candidate
retains main's exact `mcp>=1.0.0` requirement and main's `uv.lock` resolution
of `mcp==2.0.0`, including `mcp-types==2.0.0`. Main's locked 2.0.0 baseline
failed test collection because its server still imported the removed
`mcp.server.fastmcp` module; the merged server uses `MCPServer`.

The verification figures below record the original spec-branch run. On the
merged v2 candidate, the full offline suite passes 116 tests and Ruff passes.
An install that ignores `uv.lock` can still select an SDK incompatible with
the server's v2 API because the retained direct requirement permits 1.x.

The classified change analysis and official citations are in
[`SPEC-DELTA-2026-07-28.md`](SPEC-DELTA-2026-07-28.md). The implementation
release is identified by the
[official SDK v2.0.0 release notes](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0),
and API changes follow the
[official v1-to-v2 migration guide](https://py.sdk.modelcontextprotocol.io/migration/).

No deployment or live Lawmatics account was touched.

## Implementation

- Replaced v1 `FastMCP` with SDK v2 `MCPServer`; the existing decorator API,
  36 tools, three resources, three prompts, and default stdio transport remain.
- Kept the file/environment credential model, synchronous requests client,
  single-page list behavior, downstream Lawmatics OAuth flow, and conservative
  no-application-cache posture.
- Added schema-level `page >= 1` constraints to all 11 paginated list tools and
  matching client-side checks for the four specialized list implementations.
- Added PII-free reason logging for validation, credential, response-shape,
  authentication, rate-limit, and API-status rejection paths.
- Removed vendor response bodies from raised API errors and OAuth setup failure
  output so third-party data cannot leak through framework or stderr logging.
- Added a declared Python 3.10 Ruff policy and fixed the affected typing import.

## AFFECTS-US mapping

| AFFECTS-US item | Handling | Conventional commit |
| --- | --- | --- |
| Per-request version/capability metadata and removal of modern initialize | SDK v2 dual-era dispatcher; modern raw requests and modern/legacy client negotiation regressions | `feat: migrate server to MCP 2026-07-28`; `test: prove MCP 2026-07-28 conformance` |
| Required `server/discover` | Exact version, identity, capabilities, cache metadata, and sessionless behavior asserted | `test: prove MCP 2026-07-28 conformance` |
| Required `resultType` | Complete-result assertions for discovery, list, resource-read, and tool-call results | `test: prove MCP 2026-07-28 conformance` |
| Modern HTTP routing headers | In-memory raw wire tests cover `MCP-Protocol-Version`, `Mcp-Method`, and named-operation `Mcp-Name`; production remains stdio | `test: prove MCP 2026-07-28 conformance` |
| Modern subscription/listen mapping | Preserved SDK-managed list-change/resource-subscription capability declarations without adding a publisher or event bus | `feat: migrate server to MCP 2026-07-28`; `test: prove MCP 2026-07-28 conformance` |
| Capability `extensions` | Discovery proves no unused extension is advertised | `test: prove MCP 2026-07-28 conformance` |
| Required list/read cache hints | SDK defaults `ttlMs: 0`, `cacheScope: private` asserted for all applicable list/read categories | `test: prove MCP 2026-07-28 conformance` |
| Deterministic `tools/list` | Two independent listings assert identical order across all 36 tools | `test: prove MCP 2026-07-28 conformance` |
| JSON Schema 2020-12 and generalized structured content | Generated object input schemas, page minima, and structured tool results asserted | `feat: migrate server to MCP 2026-07-28`; `test: prove MCP 2026-07-28 conformance` |
| Resource-not-found `-32602` | Unknown Lawmatics resource regression asserts Invalid Params | `test: prove MCP 2026-07-28 conformance` |
| New reserved error allocation | Header mismatch `-32020`, unsupported version `-32022`, and unknown method `-32601` asserted on the wire | `test: prove MCP 2026-07-28 conformance` |

The other runtime changelog entries are classified repository-specifically in
the delta document. The four requested conventional-commit subjects are the
delta document, implementation, conformance tests, and this report.

## Sibling checks

### A. List-tool limit and order — CLEAN, with hardening

- None of the 12 `list_*` tools auto-paginates. Each call issues at most one
  vendor request, so there is no local `limit` argument that can be exceeded.
- All seven endpoints using Lawmatics' standard list query surface already
  expose `sort_by` and `sort_order`. The specialized custom-field, custom-email,
  form, and form-entry list methods retain their established documented
  page/fields parameters; unsupported sort parameters were not invented.
- Every paginated tool now declares `minimum: 1` for `page`, and every direct
  client path rejects an invalid page before HTTP. Existing contract tests
  continue to prove one request per list call and correct sort forwarding.

### B. Silent rejections — FIXED

Every application-owned client validation/rejection branch now emits a warning
with a fixed, PII-free reason before raising. Regressions cover validation and
specialized-page rejection without HTTP.

### C. Origin/CSP ceremony — N/A

This repository serves no browser pages or browser OAuth callback endpoint.
Its setup ceremony is an interactive local CLI, and the MCP entry point is
stdio-only. No origin, `Sec-Fetch-Site`, or CSP handoff surface exists.

### D. PII in logs — FIXED/CLEAN

The final logger sweep finds only fixed validation reasons plus numeric status
and HTTP method fields; no subject, email, name, token, path, vendor body, or
request body reaches a log call. Vendor response bodies were also removed from
raised API errors and token-exchange stderr output. Regressions inject an email
and name into an API failure and prove neither reaches the exception or logs.

## Verification

Baseline on the locked v1 environment:

- `uv run pytest -q`: **101 passed / 101 collected**.
- Installed SDK: **mcp 1.28.1**, latest protocol **2025-11-25**.
- `uvx ruff check .`: **6 pre-existing findings** (five non-executable
  shebangs and one typing import).

Final locked v2 environment:

- `uv sync --locked --all-groups`: **passed**.
- `uv run pytest -q`: **116 passed / 116 collected**.
- `uv run pytest -q tests/test_spec_2026_07_28.py`: **9 passed / 9 collected**.
- `uv run python tests/spec_check.py --mcp-only`: **PASS**.
- `uvx ruff check .`: **all checks passed**.
- Installed SDK: **mcp 2.0.0**, **mcp-types 2.0.0**, latest protocol
  **2026-07-28**.

The migration is verified offline and by mocked Lawmatics request contracts.
No credentials were required or read, so a live Lawmatics method/account check
remains intentionally unperformed.

## Git sandbox handoff

The sandbox denied writes to the repository's `.git` directory while creating
`refs/heads/spec-2026-07-28.lock`. The complete branch history was therefore
built in the authorized scratchpad Git database. A verified portable bundle is
exported at the task-specified `lawmatics-spec-2026-07-28.bundle` path and must
be imported into the original repository. Nothing was pushed.
