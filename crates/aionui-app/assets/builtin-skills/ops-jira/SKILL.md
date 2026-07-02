---
name: ops-jira
description: Connect to Jira Cloud — search issues, read details with comments/changelog, post comments, and transition status.
---

# Jira Ops (ops-jira)

This plugin provides Jira Cloud integration via MCP tools. Use these tools to search, read, and manage Jira issues directly.

## Setup

Before using, configure Jira credentials in AionUi Settings → Data Pilot, or create `~/.ops-jira/config.json`:

```json
{
  "JIRA_BASE_URL": "https://your-domain.atlassian.net",
  "JIRA_EMAIL": "you@company.com",
  "JIRA_API_TOKEN": "your-api-token",
  "JIRA_PROJECT_KEYS": "ZTPD"
}
```

- `JIRA_BASE_URL` — Jira Cloud URL (required)
- `JIRA_EMAIL` — Jira account email (required)
- `JIRA_API_TOKEN` — Create at https://id.atlassian.com/manage-profile/security/api-tokens (required)
- `JIRA_PROJECT_KEYS` — Optional, comma-separated project keys like `ZTPD,OPS`

Or set environment variables with the same names. Config file takes priority over env vars.

## Available Tools

### `jira_search`
Search Jira issues using JQL.
- `jql` (optional): JQL query string. If empty, searches current user's open issues.
- `maxResults` (optional): Max results (default 20, max 50).

### `jira_get_issue`
Fetch a single Jira issue by key. Includes description, latest comments, and recent changelog.
- `issueKey` (required): Jira issue key (e.g. `ZTPD-123`).

### `jira_add_comment`
Post a comment on a Jira issue.
- `issueKey` (required): Jira issue key.
- `body` (required): Comment text.

### `jira_get_transitions`
List available status transitions for a Jira issue.
- `issueKey` (required): Jira issue key.

### `jira_transition`
Transition a Jira issue to a new status.
- `issueKey` (required): Jira issue key.
- `transitionId` (required): Transition ID (number) or name.
- `comment` (optional): Comment to add during the transition.

### `jira_list_projects`
List all accessible Jira projects.

## Usage Patterns

### Find open tickets assigned to me
1. `jira_search` (empty JQL → auto-generates "assignee = currentUser() AND status IN (Open, Reopened)")
2. `jira_get_issue` on each key for details

### Investigate a specific issue
1. `jira_get_issue("ZTPD-123")` → summary, description, status, comments, changelog
2. `jira_get_transitions("ZTPD-123")` → available next statuses
3. `jira_transition("ZTPD-123", transitionId)` → change status

### Add context to a ticket
1. `jira_get_issue("ZTPD-123")` → read current state
2. `jira_add_comment("ZTPD-123", "Looking into this...")` → post update
