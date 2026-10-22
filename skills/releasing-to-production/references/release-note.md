# Release note — template

Copy everything below the line into `docs/16h/releases/<YYYY-MM-DD>-<site_key>.md`, fill every `<…>` from the `site_status` read before the push, the plan, the push and `verifying-a-deploy`, and delete what does not apply.

---

# Release to <site_key> — <YYYY-MM-DD>

**Who:** <the developer who said yes — their git `user.name`>, through the 16h dev agent

**When:** <when `site_status` said `applied`, with the time zone>

**Plan digest:** `<digest, exactly as site_plan returned it>`

## What changed

The `what_will_change` the developer heard before saying yes:

- `parts`: <what was pushed — code, database, uploads>
- `current_release`: <the release that was serving, or "null — the platform could not say">
- `restore_point`: <true>
- `database_replaced`: <true | false>

## Database replaced

<No — the live database was not touched. | Yes — replaced by the local copy taken <when>; the previous database is the restore point.>

## Verification

From `site_status(<site_key>)` after `applied`, and again five minutes later:

- `http`: <status> at <final_url> in <milliseconds> ms<; blocked_at_waf: true — the WAF answered, not the site | ; error: <error>>
- `errors_last_hour`: <count, "at least <count>" when at_cap>, against <count> in the `site_status` read before the push<; new: the top summaries>

**Restore point: kept**
