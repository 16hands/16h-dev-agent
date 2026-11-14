# 16h dev agent

Your coding agent, with access to the other side of the work: the site as it
actually runs on 16hands hosting.

Open a repo and the agent already knows which site it is, what is live, and
whether anything is erroring. When someone says "a customer hit an error this
morning" it goes and reads the live errors instead of guessing. It reads the
site's traffic, puts your change on a devsite for you to look at, and releases
to production — only when the site's owner has turned that on in the 16h
panel, and only after you have said yes to what will change.

## Install

You need `python3` (3.7 or later) and `git` on your PATH — on Windows, Git
Bash. Without them a session still starts, but silently without your repo's
facts: only the introduction to 16h arrives.

In Claude Code:

```
/plugin marketplace add 16hands/16h-dev-agent
/plugin install 16h-dev-agent@16hands
```

Then turn on auto-update, so each new version reaches you on its own:
`/plugin` → **Marketplaces** → **16hands** → **Enable auto-update**. Claude
Code leaves it off for a marketplace like this one until you turn it on.
Without it you get a new version only when you run
`/plugin marketplace update 16hands`. Either way, the agent tells you when the
version you run is behind.

For Codex, in your terminal:

```
codex plugin marketplace add 16hands/16h-dev-agent
```

then, inside Codex:

1. `/plugins` → install **16h-dev-agent**.
2. `/hooks` → trust the 16h-dev-agent session-start hook. You do this once,
   and again if an update changes the hook.

Do not skip step 2. Codex runs no plugin hook until you have trusted it, and
without the hook a session starts knowing nothing about your repo: no first
call to 16h, no project named, until you ask.

In Claude Code and in Codex alike, the install brings the hook, the skills
and the connection to 16h. Nothing is added to your project to make it work —
no config files, no per-repo setup.

## Signing in

Access is invite-only: your contact at 16hands creates your login and chooses
which clients you can see. The first time the agent connects to 16h, a browser
opens for you to sign in. There are no keys or tokens to copy, and nothing
secret lives in this repository.

## What happens when you open a repo

1. **The session-start hook runs.** It looks at the folder on your machine and
   nowhere else: the git remote, the branch, the hostnames in `.env` or
   `wp-config.php`, the folder name and the kind of app. No token, no network,
   nothing written. It hands those facts to the agent with a short
   introduction to 16h.
2. **The agent's first call is `site_status`**, with those facts.
3. **When 16h knows the repo**, the agent opens by naming the project: the
   client, production, the devsites, the last push, errors in the last hour,
   and whether the site is reachable. Then it does what you asked.
4. **When nothing on 16h matches**, the agent lists the sites you can see and
   asks once which one this repo is. When the repo has a git remote, your
   answer is remembered on 16h by that remote, not in the repo — so the next
   session, in either agent, opens with the project named.

## Skills

Each skill is named for a moment. Say what is happening in your own words and
the matching skill takes over:

| Skill | When it applies |
|---|---|
| `using-16h` | Every session — the hook injects it. The first call, the moments below, and the rules that never change |
| `debugging-a-live-site` | "it's erroring", "the site is down", "slow", "500", "customers can't check out", "a client emailed", "why is the site 500ing" |
| `reading-traffic` | "who's hitting the site", "is it a bot", "what happened at 2pm", "are our emails going out", "did the cron run" |
| `pushing-to-staging` | "put this on staging", "push my changes", "give me a devsite", "I want to see it before it goes live", "send the fix to the devsite" |
| `releasing-to-production` | "deploy to prod", "go live", "ship it", "push to production", "release this" |
| `verifying-a-deploy` | After any push, and "is it up?", "did that work?", "is the deploy done?" |

Two of them hold a line. `debugging-a-live-site` changes no code until the
error is named from the platform's logs. `releasing-to-production` goes ahead
only when the site's owner has turned on agent pushes in the 16h panel, and
only after you have heard every line of what will change and said yes.

## Records in `docs/16h/`

Two skills leave a record in your repo:

- `docs/16h/releases/` — a note after every production push: who said yes,
  when, the plan's digest, what changed, and how the site answered afterwards.
- `docs/16h/investigations/` — a note when the agent names a live-site fault:
  the report, the evidence lines from the logs, the hypothesis, and what was
  changed or ruled out.

They are yours to commit or not, and the next session can read them. A push
also writes `.deployignore`, the list of what the upload leaves out, yours to
keep like a `.gitignore`. A Laravel, Statamic or Symfony push also keeps
`.env.16h`, your own values for the devsite, and adds its one line to
`.gitignore`: the file is never committed, and its values are never quoted in
a record or a message. Nothing else is ever written to your repo, never a
secret anywhere else, and the plugin needs none of it to work.

## What it deliberately cannot do

No SSH, no database access, no server filesystem. The tools are the entire
surface, every call is checked against what you have been granted, and every
call is recorded. A tool that refuses is telling you the truth about your
access.

## Other agents

The skills follow the [Agent Skills](https://agentskills.io) standard, so
agents that read it — Cursor and GitHub Copilot among them — can use the
folders in `skills/`. Connect them to 16h through its standard remote MCP
endpoint:

```
https://mcp.16h.io/mcp
```

Add that as an HTTP MCP server. Those agents have no session-start hook from
this plugin yet, so open a session by asking for the site's status on 16h.

## Support

Talk to your contact at 16hands.
