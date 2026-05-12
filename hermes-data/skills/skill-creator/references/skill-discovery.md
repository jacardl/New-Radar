# Skill Discovery — When skill_view Fails

## Problem

`skill_view(name="中文名")` or `skills_list(category="中文分类")` can fail silently or return empty results due to Unicode/encoding issues in the MCP skill registry. The skill exists on disk but isn't discoverable through the tools.

## Diagnosis Checklist

When `skill_view` returns `Skill not found` for a skill you believe exists:

1. **Try the terminal search** — `skill_view` failure ≠ skill doesn't exist
2. **List directories** to find the skill path:
   ```bash
   find /app/.hermes/skills -maxdepth 3 -type d | sort
   find /app/hermes-agent/skills -maxdepth 2 -type d | sort
   ```
3. **Search by content** if you know part of the description:
   ```bash
   grep -r "关键词研究" /app/.hermes/skills/ --include="*.md" -l
   ```
4. **Check for name mapping issues** — some skills have an internal slug (e.g. `sentiment-data-collection`) that differs from their display name (`舆情数据采集规范`)

## Two-Layer Skill Library

| Layer | Path | Tool Access |
|-------|------|-------------|
| MCP registry (skills_list) | Virtual — served by MCP | `skills_list()`, `skill_view()` |
| On-disk library | `/app/.hermes/skills/` (user skills) | `search_files`, `terminal` |
| On-disk library | `/app/hermes-agent/skills/` (built-in) | `search_files`, `terminal` |

The MCP layer only surfaces ~20 skills. The full library has 90+ skills on disk.

## Action Plan When Stuck

```
skill_view fails → terminal find → locate actual slug → skill_view with slug
                                       ↓
                              If still not found:
                              skills_list(category=X) to cross-check
                              grep -r "description fragment" /app/.hermes/skills/
```

## Known Unicode Pitfalls

- Skills with Chinese display names may not resolve via `skill_view(name="...")` — always verify via filesystem
- `skills_list` with `category` parameter may not filter correctly for non-ASCII categories — use unfiltered `skills_list()` and grep results manually
- The `skills_list` output `available_skills` array only shows MCP-layer skills, not all disk skills
