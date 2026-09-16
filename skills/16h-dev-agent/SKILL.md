---
name: 16h-dev-agent
description: Use when working on a site hosted by 16 Hands — investigating an error a client reported, checking a site's behaviour, or diagnosing something that only shows up in production. Provides the 16h tools and the discipline for using them.
---

# Working on a 16h-hosted site

You have tools from the `16h` MCP server. You are scoped to specific clients,
and every call is recorded against your identity. If a tool refuses, you lack
that access — say so plainly and stop; do not retry or try another client key.

## Investigating "the client reported an error"

1. `read_errors` with the client key and a window that covers when it was
   reported (`minutes`). Read the `summary` lines first; pull `message` for a
   full stack trace once you know which error matters.
2. Read the `node` field before concluding. The same error on every node is a
   code or data problem; on one node it is that machine.
3. Only change code once you can **name** the error. An error you cannot find
   in the logs is one you have not reproduced.

## What this does not give you

No SSH, no database access, no filesystem on the servers. These tools are the
whole surface. If a task genuinely needs more, the answer is to ask 16 Hands,
not to work around it.

## Deploys

Staged deploys and post-deploy checks are coming in a later release. Until
then, deploying is still done however your team does it today.
