# 16h dev agent

Your coding agent, with access to the other side of the work: the site as it
actually runs on 16 Hands hosting.

Today it reads a client's live errors from the platform's aggregated logs, so
when someone says "a customer hit an error this morning" the agent can go and
look instead of guessing. Staged deploys and post-deploy checks follow.

## Install

In Claude Code:

```
/plugin marketplace add 16hands/16h-dev-agent
/plugin install 16h-dev-agent@16hands
```

That installs the tools and the workflow skill. Nothing is added to your
project — no config files, no per-repo setup.

## Signing in

Access is invite-only: your contact at 16 Hands creates your login and chooses
which clients you can see. The first time a tool runs, a browser opens for you
to sign in. There are no keys or tokens to copy, and nothing secret lives in
this repository.

## What you get

| Tool | What it does |
|---|---|
| `read_errors` | Recent errors for one of your clients, across the whole fleet, newest first |

Ask in plain language — "read recent errors for `<client>`" — rather than
calling tools by name.

## What it deliberately cannot do

No SSH, no database access, no server filesystem. The tools are the entire
surface, every call is checked against what you have been granted, and every
call is recorded. A tool that refuses is telling you the truth about your
access.

## Other agents

The server is a standard remote MCP endpoint, so anything that speaks MCP can
use it:

```
https://mcp.16h.io/mcp
```

For Codex, Cursor and similar, add that as an HTTP MCP server. The workflow
skill in `skills/` is worth reading into your project instructions if your
tool does not support Claude Code plugins.

## Support

Talk to your contact at 16 Hands.
