# Lawmatics MCP server

[![CI](https://github.com/RosenAdvertising/lawmatics-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/RosenAdvertising/lawmatics-mcp/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-F59E0B.svg)](LICENSE)
[![MCP 2026-07-28](https://img.shields.io/badge/MCP-2026--07--28-7C3AED.svg)](https://modelcontextprotocol.io)
[![36 tools](https://img.shields.io/badge/tools-36-22C55E.svg)](https://github.com/RosenAdvertising/lawmatics-mcp)

Connect Claude and other MCP clients to Lawmatics to manage matters, contacts, tasks, notes, events and intake forms.

Lawmatics MCP server is a [Model Context Protocol](https://modelcontextprotocol.io) server for Lawmatics, the legal CRM and intake platform. It registers 36 tools that read and write Lawmatics data. It runs over stdio by default, for desktop clients such as Claude Desktop, and offers an opt-in stateless Streamable HTTP mode that implements MCP specification 2026-07-28. Lawmatics credentials stay on the machine that runs the server: they come from the setup command and a private file in your home directory, never from the client.

## Features

- **Matters**: list, look up, find by phone, email or name, create and update matters (the `/prospects` resource in the Lawmatics API).
- **Contacts**: list, look up, create and update contacts.
- **Tasks**: list, look up, create, update and complete tasks, and list task statuses.
- **Notes and events**: list, look up, create and update notes and events.
- **Interactions**: list interactions and log new ones.
- **Intake forms**: list forms and their entries, and submit a form.
- **Reference data**: firm users, custom fields and custom emails.

## Tools

The server registers 36 tools.

<details>
<summary>All 36 tools</summary>

| Category | Tools |
| --- | --- |
| Identity | `get_current_user`, `list_users`, `get_user` |
| Matters | `list_matters`, `get_matter`, `create_matter`, `update_matter`, `find_matter` |
| Contacts | `list_contacts`, `get_contact`, `create_contact`, `update_contact` |
| Tasks | `list_tasks`, `get_task`, `create_task`, `update_task`, `complete_task`, `list_task_statuses` |
| Notes | `list_notes`, `get_note`, `create_note`, `update_note` |
| Events | `list_events`, `get_event`, `create_event`, `update_event` |
| Custom fields | `list_custom_fields`, `get_custom_field` |
| Interactions | `list_interactions`, `create_interaction` |
| Custom emails | `list_custom_emails`, `get_custom_email` |
| Forms | `list_forms`, `get_form`, `list_form_entries`, `submit_form` |

</details>

### Prompts and resources

The server also registers three prompts and three resources.

- Prompt `triage_new_leads`: reviews recent prospects and recommends prioritized intake actions.
- Prompt `review_pipeline_health`: analyzes stage volume, stale prospects, and conversion bottlenecks.
- Prompt `sweep_stale_follow_ups`: prepares concrete follow-up work using a configurable staleness threshold.
- Resource `lawmatics://users`: read-only JSON reference data for firm users and staff.
- Resource `lawmatics://custom-fields`: read-only JSON metadata for configured CRM custom fields.
- Resource `lawmatics://security-notes`: guidance on CRM sensitivity, OAuth tokens, rate limits, and prompt injection.

## Requirements

- Python 3.10 or later.
- A Lawmatics developer app, with Developer Settings enabled for your firm by Lawmatics support (`support@lawmatics.com`).
- An MCP client such as Claude Desktop.

## Installation

Install [uv](https://docs.astral.sh/uv/), then clone the repository and install its locked dependencies:

```bash
git clone https://github.com/RosenAdvertising/lawmatics-mcp.git
cd lawmatics-mcp
uv sync --locked
```

## Configuration

Lawmatics uses OAuth. Setup runs once, stores a non-expiring bearer token, and verifies it.

1. Ask `support@lawmatics.com` to enable Developer Settings for your firm.
2. In Lawmatics, create an OAuth developer app.
3. Register this redirect URI with the app unless you need a different local callback:

   ```text
   http://127.0.0.1:8124/callback
   ```

   Setup accepts only an HTTP callback on `127.0.0.1` with an explicit port and path. `localhost`, IPv6 and external callbacks are rejected, so register the exact `127.0.0.1` redirect with Lawmatics.

4. Run setup:

   ```bash
   uv run lawmatics-mcp-setup
   ```

5. Enter the client ID, client secret and redirect URI. Setup binds the callback, then prints an authorization URL:

   ```text
   https://app.lawmatics.com/oauth/authorize?client_id=...&redirect_uri=...&response_type=code&state=...
   ```

6. Open the URL and approve access. Setup receives the callback, verifies its random state, and exchanges the code at:

   ```text
   POST https://api.lawmatics.com/oauth/token
   ```

   An occupied callback port, or an invalid or missing state, stops authorization.

7. Verify the connection:

   ```bash
   uv run lawmatics-mcp-verify
   ```

Server messages that say to run `lawmatics-mcp-setup` mean `uv run lawmatics-mcp-setup` from your clone.

Lawmatics tokens do not expire, and there is no refresh token or refresh flow. If a token is revoked or invalid, re-run setup.

Setup writes the credentials to `~/.lawmatics-mcp/.env`, in a `0700` directory with a `0600` file. The file is replaced atomically after private permissions are established; if they cannot be established, setup stops without writing new secrets. On Windows, the file is stored in the user's profile and protected by Windows' default per-user access rules.

```dotenv
LAWMATICS_CLIENT_ID=...
LAWMATICS_CLIENT_SECRET=...
LAWMATICS_REDIRECT_URI=http://127.0.0.1:8124/callback
LAWMATICS_ACCESS_TOKEN=...
```

The server reads these variables. Values already set in the process environment take precedence over the file.

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `LAWMATICS_ACCESS_TOKEN` | Yes (saved by setup) | From `~/.lawmatics-mcp/.env` | Bearer token sent to the Lawmatics API on every authenticated request. |
| `LAWMATICS_CLIENT_ID` | No (saved by setup) | From `~/.lawmatics-mcp/.env` | OAuth client ID recorded by setup. The server does not use it when calling the API. |
| `LAWMATICS_CLIENT_SECRET` | No (saved by setup) | From `~/.lawmatics-mcp/.env` | OAuth client secret recorded by setup. The server does not use it when calling the API. |
| `LAWMATICS_REDIRECT_URI` | No (saved by setup) | From `~/.lawmatics-mcp/.env` | Redirect URI recorded by setup. The server does not use it when calling the API. |
| `LAWMATICS_MCP_CONFIG_DIR` | No | `~/.lawmatics-mcp` | Directory that holds the `.env` file. On Windows it must be inside the user profile. |

## Usage with Claude Desktop

Add the server to Claude Desktop's configuration file (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "lawmatics": {
      "command": "uv",
      "args": ["run", "--locked", "--directory", "/absolute/path/to/lawmatics-mcp", "lawmatics-mcp"]
    }
  }
}
```

Replace `/absolute/path/to/lawmatics-mcp` with the path of your clone, then restart Claude Desktop. Any other stdio MCP client uses the same command and arguments.

## HTTP mode

Stdio is the default. Set `LAWMATICS_MCP_TRANSPORT=streamable-http` to serve the stateless Streamable HTTP transport from MCP specification 2026-07-28 at `/mcp`. Each request stands alone: no initialization handshake and no `Mcp-Session-Id`. Clients on earlier protocol versions are served on the same endpoint.

> **Security: this endpoint has no authentication and no TLS.** Anyone who can reach the port can run every tool, including write tools, with this server's vendor credentials. Keep the default loopback bind (`127.0.0.1`), or put the server behind an authenticating TLS proxy on a private network. `LAWMATICS_MCP_ALLOWED_HOSTS` and `LAWMATICS_MCP_ALLOWED_ORIGINS` protect against browser DNS rebinding, not against direct callers. A proxy in front of it needs connection and idle timeouts: a legacy-style `GET /mcp` with `Accept: text/event-stream` holds a stream open until the client disconnects.

| Variable | Default | Purpose |
| --- | --- | --- |
| `LAWMATICS_MCP_TRANSPORT` | `stdio` | `stdio` or `streamable-http`. An empty value selects `stdio`. |
| `LAWMATICS_MCP_HOST` | `127.0.0.1` | Bind address. An empty value selects `127.0.0.1`. `127.0.0.1`, `localhost` and `::1` use the SDK's built-in Host and Origin checks; any other value requires `LAWMATICS_MCP_ALLOWED_HOSTS`. |
| `PORT` | `8080` | Port; must be an integer. |
| `LAWMATICS_MCP_ALLOWED_HOSTS` | unset | Comma-separated `Host` header values accepted on a non-loopback bind, such as `mcp.example.com:8080` or `mcp.example.com:*`. |
| `LAWMATICS_MCP_ALLOWED_ORIGINS` | unset | Comma-separated `Origin` values accepted on a non-loopback bind, such as `https://client.example.com`. Requests without an `Origin` header are accepted. |

Lawmatics credentials come from the same configuration as stdio (see [Configuration](#configuration)), never from the request.

```bash
LAWMATICS_MCP_TRANSPORT=streamable-http PORT=8080 uv run --locked lawmatics-mcp
```

Point the MCP client at `http://127.0.0.1:8080/mcp`.

## Error handling

A failed tool call returns an MCP error result (`isError`) with a fixed message. The server never passes a Lawmatics response body, a request URL, a credential or a rejected input value back to the client.

| Situation | What the tool returns |
| --- | --- |
| Credentials missing | "Lawmatics credentials are missing. Run lawmatics-mcp-setup or set LAWMATICS_ACCESS_TOKEN." |
| Authentication rejected (HTTP 401) | "Lawmatics authentication was rejected or expired. Reauthorize with lawmatics-mcp-setup." |
| Access denied (HTTP 403) | "Lawmatics access denied: the connected account lacks permission for this action (or the authorization expired; re-run lawmatics-mcp-setup if so)." |
| Rate limited (HTTP 429) | "Lawmatics rate limit reached. Retry after N seconds; this client does not auto-retry." N is the numeric `Retry-After` value; without one the message reads "Retry later; this client does not auto-retry." |
| Record not found (HTTP 404) | "The requested Lawmatics record was not found (HTTP 404). Check the record ID." |
| Any other HTTP error, or a success response that is not a JSON object | "Lawmatics API request failed (HTTP 500): request could not be processed." The status varies, and the text after the colon is one of a few fixed reasons (request parameters were invalid, the account is not allowed to perform this action, the request conflicts with the current record, response was not valid JSON, response had an unexpected shape). |
| Timeout on a read | "Lawmatics request timed out. Retry the read when the service is available." |
| Timeout on a write | "Lawmatics request timed out. The outcome is unknown; check whether the change completed before retrying." |
| Connection failure on a read | "Could not connect to Lawmatics. Check connectivity, then retry the read." |
| Connection failure on a write | "Could not connect to Lawmatics. The outcome is unknown; check whether the change completed before retrying." |
| Invalid arguments | A message such as "Invalid arguments: 'page' must be integer >= 1." or "Invalid arguments: page must be 1 or greater." |
| Anything else | "Error executing tool" followed by the tool name, with no detail. |

Every Lawmatics request has a 30-second timeout, and the server never retries: a rate-limited, timed-out or failed request is returned at once. The write tools are `create_matter`, `update_matter`, `create_contact`, `update_contact`, `create_task`, `update_task`, `complete_task`, `create_note`, `update_note`, `create_event`, `update_event`, `create_interaction` and `submit_form`. A failed resource read returns the same classified message, or "Unable to read Lawmatics users. Check the connection and authorization." (for custom fields, "Unable to read Lawmatics custom fields. Check the connection and authorization.").

Missing credentials are reported when a tool is called, not at startup. At startup the server exits with a message on stderr and a non-zero status when `LAWMATICS_MCP_TRANSPORT` is neither `stdio` nor `streamable-http`, when `PORT` is not an integer, or when a non-loopback `LAWMATICS_MCP_HOST` is set without `LAWMATICS_MCP_ALLOWED_HOSTS`.

## API notes

- Base URL: `https://api.lawmatics.com/v1`
- On `429`, the server raises a rate-limit error with any `Retry-After` value
  returned by Lawmatics and does not auto-sleep.
- Auth: `Authorization: Bearer <LAWMATICS_ACCESS_TOKEN>` on every authenticated request.
- `submit_form` is unauthenticated and intentionally sends no bearer header.
- Matters in the Lawmatics UI are `/v1/prospects` in the API. All matter tools and finders use `/prospects`, never `/matters`.
- Money fields are integer cents, such as `estimated_value_cents`, `actual_value_cents`, and `lead_cost_cents`.
- List tools support `page`, `fields`, `sort_by`, `sort_order`, `filter_by`, `filter_on`, and `filter_with` where the official docs support them.

## Testing

The test suite runs offline and needs no Lawmatics account: every Lawmatics API call is answered by a test double for the `requests` session. It covers each tool's request and response contract, list parameters and filters, path-identifier validation, error handling, the OAuth setup flow and loopback callback, credential file handling, the stdio server, and the Streamable HTTP transport including the 2026-07-28 wire format, Host and Origin checks and stateless requests.

```bash
uv sync --locked
uv run --locked pytest -q
```

CI runs the suite on every push and pull request to `main`.

The tools follow Lawmatics's published API documentation and have not yet been run against a live Lawmatics account.

## License

MIT. See [LICENSE](LICENSE).
