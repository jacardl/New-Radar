---
name: github-skill-library
description: Load, verify, and manage skills sourced from remote GitHub repositories. Covers GitHub raw URLs vs GitHub API vs browser fallback, base64 decoding, skill verification, and memory integration. Use when the user says "learn this skill", shares a GitHub link to a SKILL.md, or asks to install a skill from a repo.
---

# GitHub Skill Library — Load Skills from Remote Repos

## When to use

- User says "learn this skill" with a GitHub URL
- User shares a link to a `.md` file in a GitHub repo and wants you to "save it"
- You need to install a skill from a third-party repo (e.g. `decolua/9router`)

## Workflow

### Step 1 — Determine the URL type

| URL pattern | Method |
|---|---|
| `https://raw.githubusercontent.com/.../SKILL.md` | `curl -sL --max-time 20 <url>` |
| `https://github.com/.../SKILL.md` (blob page) | GitHub API → base64 decode |
| `https://github.com/.../SKILL.md` (rendered) | Browser CDP fallback |

### Step 2 — Fetch the content

**Try raw URL first (fastest):**
```bash
curl -sL --max-time 20 "https://raw.githubusercontent.com/user/repo/refs/heads/main/path/SKILL.md"
```

**If raw times out (common for large repos), use GitHub API:**
```bash
# Get file metadata + base64 content
curl -sL --max-time 20 "https://api.github.com/repos/user/repo/contents/path/SKILL.md?ref=branch"

# Decode the base64 content
echo "<content_from_above>" | base64 -d
```

**If GitHub API also times out, use browser CDP:**
```bash
browser_navigate(url="https://github.com/user/repo/blob/branch/path/SKILL.md")
# Then extract content via DOM reading
```

### Step 3 — Verify the skill works

Do not just store the content. **Verify** it with a quick functional test:

- For search/fetch skills: run a minimal API call
- For other skills: check skill frontmatter is valid YAML

### Step 4 — Store credentials/config if needed

If the skill requires API keys or endpoints (e.g. 9Router), store in memory via `memory` tool, not hardcoded.

## Pitfalls

- **GitHub raw CDN sometimes times out** even when the repo is accessible — retry via GitHub API
- **GitHub API has lower rate limits** for unauthenticated requests; if you hit 403, fall back to raw URL or browser
- **Blob pages are HTML**, not raw markdown — do not try to parse them as raw content
- **base64 padding**: content field in GitHub API is base64 encoded; missing padding is normal, `base64 -d` handles it
- **Large skills (>100KB)** may exceed output truncation — fetch only the SKILL.md, not supporting files automatically

## Example: Loading 9Router skills

```bash
# Step 1: Try raw
curl -sL --max-time 20 "https://raw.githubusercontent.com/decolua/9router/master/skills/9router-web-search/SKILL.md"

# Step 2: If timeout, use API
curl -sL --max-time 20 "https://api.github.com/repos/decolua/9router/contents/skills/9router-web-search/SKILL.md"
# Then: echo "$content" | base64 -d

# Step 3: Verify
curl -X POST "$NINEROUTER_URL/v1/search" \
  -H "Authorization: Bearer $NINEROUTER_KEY" \
  -d '{"model":"search-combo","query":"test","max_results":1}'

# Step 4: Store in memory
memory add target=memory content="五、9Router 配置: URL = ..., Key = ..."
```
