# lawmatics-mcp

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-F59E0B.svg)](https://opensource.org/licenses/MIT)
[![36 tools](https://img.shields.io/badge/tools-36-22C55E.svg)](https://github.com/RosenAdvertising/lawmatics-mcp)
[![MCP](https://img.shields.io/badge/MCP-compatible-7C3AED.svg)](https://modelcontextprotocol.io)

> [!IMPORTANT]
> **Built to spec — not yet verified against a live Lawmatics account.**
> This server was built from Lawmatics's public API documentation and passes its full offline test suite, but we don't currently have Lawmatics API access to verify behavior against the live API. Endpoint paths, parameters, and response shapes follow the documented spec. If you hit a discrepancy, please open an issue.

MCP server for Lawmatics legal CRM and intake. It exposes the confirmed v0.1 API surface for identity, matters, contacts, tasks, notes, events, custom fields, interactions, custom emails, and forms.

## Requirements

- Python 3.10+
- MCP Python SDK 2.x (`mcp>=2.2,<3`)
- A Lawmatics developer app
- Developer Settings enabled by Lawmatics support: contact `support@lawmatics.com`
- Claude Desktop or another MCP-compatible client

## Install

From a published package:

```bash
pip install lawmatics-mcp
```

From this source tree:

```bash
uv build
pip install dist/lawmatics_mcp-0.1.0-py3-none-any.whl
```

## Setup

1. Ask `support@lawmatics.com` to enable Developer Settings for your firm.
2. In Lawmatics, create an OAuth developer app.
3. Use this redirect URI unless you need a different local callback:

   ```text
   http://127.0.0.1:8124/callback
   ```

4. Run setup:

   ```bash
   lawmatics-mcp-setup
   ```

5. Enter the client ID, client secret, and redirect URI. The setup command prints an authorization URL:

   ```text
   https://app.lawmatics.com/oauth/authorize?client_id=...&redirect_uri=...&response_type=code&state=...
   ```

6. Register the exact HTTP loopback redirect with Lawmatics. Setup binds that
   callback before displaying the authorization URL. Open the URL and approve
   access; setup receives the callback and verifies its random state before exchanging
   the code at:

   ```text
   POST https://api.lawmatics.com/oauth/token
   ```

7. Verify:

   ```bash
   lawmatics-mcp-verify
   ```

Lawmatics tokens are non-expiring bearer tokens. There is no refresh token and no refresh flow. If a token is revoked or invalid, re-run `lawmatics-mcp-setup`.

## Claude Desktop

Add this to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "lawmatics": {
      "command": "lawmatics-mcp"
    }
  }
}
```

Restart Claude Desktop after saving the config.

## Environment

Runtime configuration is loaded from `~/.lawmatics-mcp/.env`:

```dotenv
LAWMATICS_CLIENT_ID=...
LAWMATICS_CLIENT_SECRET=...
LAWMATICS_REDIRECT_URI=http://127.0.0.1:8124/callback
LAWMATICS_ACCESS_TOKEN=...
```

The setup command writes this file with mode `0600` in a `0700` config directory. Process environment variables override file values.

## API Notes

- Base URL: `https://api.lawmatics.com/v1`
- On `429`, the server raises a rate-limit error with any `Retry-After` value
  returned by Lawmatics and does not auto-sleep.
- Auth: `Authorization: Bearer <LAWMATICS_ACCESS_TOKEN>` on every authenticated request.
- `submit_form` is unauthenticated and intentionally sends no bearer header.
- Matters in the Lawmatics UI are `/v1/prospects` in the API. All matter tools and finders use `/prospects`, never `/matters`.
- Money fields are integer cents, such as `estimated_value_cents`, `actual_value_cents`, and `lead_cost_cents`.
- List tools support `page`, `fields`, `sort_by`, `sort_order`, `filter_by`, `filter_on`, and `filter_with` where the official docs support them.

## Tools

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

## Prompts & resources

- Prompt `triage_new_leads`: reviews recent prospects and recommends prioritized intake actions.
- Prompt `review_pipeline_health`: analyzes stage volume, stale prospects, and conversion bottlenecks.
- Prompt `sweep_stale_follow_ups`: prepares concrete follow-up work using a configurable staleness threshold.
- Resource `lawmatics://users`: read-only JSON reference data for firm users and staff.
- Resource `lawmatics://custom-fields`: read-only JSON metadata for configured CRM custom fields.
- Resource `lawmatics://security-notes`: guidance on CRM sensitivity, OAuth tokens, rate limits, and prompt injection.

## v0.2 - deferred pending live verification

These resources or operations are intentionally not included in v0.1 despite partial evidence elsewhere, because they need live verification against the official API before being exposed:

- Companies
- Expenses
- Time entries
- Matter sub-status
- Folders
- `email_addresses` and `phone_numbers`
- Collections
- Task subtasks and comments
- Deletes
- User writes and custom-field writes
- Contact/company finders

## Testing

```bash
uv run --offline --locked --with pytest pytest -q
uv run --offline --locked python tests/spec_check.py --mcp-only
uv lock --check --offline
```

The pytest fixture uses fake credentials and a temporary config directory.
Vendor requests are mocked; protocol tests use an in-process HTTP transport.
These checks do not verify live Lawmatics behavior.

## License

MIT

Setup accepts only HTTP callbacks on `127.0.0.1`, with an explicit port and path.
`localhost`, IPv6 and external callbacks are rejected. Update any previous
`localhost` registration with Lawmatics to the exact `127.0.0.1` redirect. An occupied callback port or invalid/missing state stops authorization.
Credential files are atomically replaced after private permissions are established;
a permissions failure stops setup without writing new secrets.
