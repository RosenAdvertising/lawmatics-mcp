# lawmatics-mcp

> [!IMPORTANT]
> **Built to spec — not yet verified against a live Lawmatics account.**
> This server was built from Lawmatics's public API documentation and passes its full offline test suite, but we don't currently have Lawmatics API access to verify behavior against the live API. Endpoint paths, parameters, and response shapes follow the documented spec. If you hit a discrepancy, please open an issue.

MCP server for Lawmatics legal CRM and intake. It exposes the confirmed v0.1 API surface for identity, matters, contacts, tasks, notes, events, custom fields, interactions, custom emails, and forms.

## Requirements

- Python 3.10+
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
   http://localhost:8124/callback
   ```

4. Run setup:

   ```bash
   lawmatics-mcp-setup
   ```

5. Enter the client ID, client secret, and redirect URI. The setup command prints an authorization URL:

   ```text
   https://app.lawmatics.com/oauth/authorize?client_id=...&redirect_uri=...&response_type=code
   ```

6. Open that URL, approve access, paste the returned code, and setup exchanges it at:

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
LAWMATICS_REDIRECT_URI=http://localhost:8124/callback
LAWMATICS_ACCESS_TOKEN=...
```

The setup command writes this file with mode `0600` in a `0700` config directory. Process environment variables override file values.

## API Notes

- Base URL: `https://api.lawmatics.com/v1`
- Rate limit: 50 requests per minute per firm
- On `429`, Lawmatics returns `Retry-After` such as `60`; this server raises the error and does not auto-sleep.
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
uv run --with pytest pytest -q
uv build
```

The pytest suite mocks all HTTP and must not use real credentials or make network calls.

Certification beyond the pytest suite (static, secrets, coverage, live smoke and write
tiers) runs from a private cert pack with an internal MCP test toolkit; those artifacts
are intentionally not part of this repository. The spec-check tier is skipped until
Lawmatics publishes an OpenAPI spec. Live tiers run once API credentials are provisioned.

## License

MIT
