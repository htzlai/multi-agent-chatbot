# Project-Wide Cleanup Plan

> Generated: 2026-02-27
> Prerequisite: Execute BEFORE `backend-refactor.md` — clean slate first
> Principle: Claude Code 最佳实践 — CLAUDE.md 是唯一权威源，其余 .md 要么服务于不同受众，要么删除

---

## 1. Current .md File Inventory (13 files, ~4332 lines)

| File | Lines | Audience | Verdict |
|------|-------|----------|---------|
| `CLAUDE.md` (root) | 94 | Claude Code | **KEEP** — authoritative spec |
| `assets/backend/CLAUDE.md` | 170 | Claude Code | **KEEP** — backend-specific extension |
| `AGENTS.md` | 77 | AI agents (Codex etc.) | **KEEP** — distinct audience |
| `README.md` (root) | 144 | End users | **KEEP** — public setup guide |
| `assets/backend/API_DOCS.md` | 1017 | Frontend devs | **KEEP** — primary API reference |
| `.claude/plans/backend-refactor.md` | 575 | Claude Code | **KEEP** — active plan |
| `assets/README.md` | 53 | Nobody | **DELETE** — redundant with root README |
| `assets/backend/README.md` | 64 | Nobody | **DELETE** — redundant with CLAUDE.md |
| `assets/frontend/README.md` | 53 | Nobody | **DELETE** — no unique content |
| `assets/development.md` | 160 | Ops | **MERGE → root README, then DELETE** |
| `assets/backend/CODE_REVIEW.md` | 601 | Reference | **DELETE** — findings absorbed into plan |
| `assets/backend/RAG_ANALYSIS.md` | 1492 | Reference | **DELETE** — findings absorbed into plan |
| `plans/refactor_preparation_guide.md` | 518 | Planning | **DELETE** — superseded by .claude/plans/ |

**After cleanup: 6 files kept, 7 files deleted = ~2941 lines removed**

---

## 2. Files to DELETE

### 2.1 Redundant .md Files

| File | Reason |
|------|--------|
| `assets/README.md` | 53 lines of generic Docker troubleshooting, all covered in root README |
| `assets/backend/README.md` | 64 lines of vague feature list, fully covered by CLAUDE.md |
| `assets/frontend/README.md` | 53 lines, component list is the only unique content (1 line) |
| `assets/development.md` | 160 lines, duplicates root README setup steps (merge unique bits first) |
| `assets/backend/CODE_REVIEW.md` | 601 lines, all actionable findings already in backend-refactor.md §5-§7 |
| `assets/backend/RAG_ANALYSIS.md` | 1492 lines, Part 1 absorbed into plan §3, Part 2 is outdated (wrong chunk_size) |
| `plans/refactor_preparation_guide.md` | 518 lines, superseded by .claude/plans/backend-refactor.md |

### 2.2 Dead Frontend Assets

| File | Reason |
|------|--------|
| `assets/frontend/public/file.svg` | Default Next.js scaffold, zero references in codebase |
| `assets/frontend/public/globe.svg` | Same |
| `assets/frontend/public/next.svg` | Same |
| `assets/frontend/public/vercel.svg` | Same |
| `assets/frontend/public/window.svg` | Same |

### 2.3 Build Artifacts (should never be tracked)

| Path | Reason |
|------|--------|
| `assets/tests/.pytest_cache/` | pytest cache directory |
| `assets/backend/.claude/plan/` | Empty directory, stale |

---

## 3. Content to MERGE Before Deletion

### 3.1 `assets/development.md` → root `README.md`

Unique content to extract before deleting:

```markdown
## Troubleshooting (append to root README)

| Issue | Solution |
|-------|----------|
| HuggingFace gated model access | Set `HF_TOKEN` env var, accept model license on HF |
| GPU memory insufficient | Run `sudo nvidia-smi -r` or reboot to flush UMA memory |
| Container OOM killed | Check `docker stats`, reduce model quantization |
```

---

## 4. .gitignore Updates

### 4.1 Root `.gitignore` (create if not exists)

```gitignore
# Claude Code runtime state
.claude/checkpoints.log
.claude/settings.json
```

Note: `.claude/plans/` and `CLAUDE.md` SHOULD be tracked — they're project specs.

### 4.2 `assets/.gitignore` (append)

```gitignore
# Claude Code
**/.claude/checkpoints.log
**/.claude/settings.local.json
**/.claude/plan/

# Build artifacts
**/.pytest_cache/
frontend/tsconfig.tsbuildinfo
```

---

## 5. CLAUDE.md Updates

### 5.1 Root `CLAUDE.md` — Update Key Files section

Replace:
```markdown
## Key Files
- Refactoring guide: `plans/refactor_preparation_guide.md`
- API docs: `assets/backend/API_DOCS.md`
- Development guide: `assets/development.md`
```

With:
```markdown
## Key Files
- Refactoring plan: `.claude/plans/backend-refactor.md`
- API docs: `assets/backend/API_DOCS.md`
```

### 5.2 Backend `CLAUDE.md` — No changes needed

Already accurate. The refactoring phases checklist will be updated after execution.

---

## 6. Files to KEEP (and why)

| File | Lines | Why Keep |
|------|-------|----------|
| `CLAUDE.md` (root) | 94 | Authoritative project spec for Claude Code |
| `assets/backend/CLAUDE.md` | 170 | Backend-specific extension, module graph, route map |
| `AGENTS.md` | 77 | Distinct audience (non-Claude AI agents) |
| `README.md` (root) | 144 | Public-facing setup guide for end users |
| `assets/backend/API_DOCS.md` | 1017 | Primary API reference for frontend devs |
| `.claude/plans/backend-refactor.md` | 575 | Active refactoring plan |

---

## 7. Execution Steps

### Step 1: Merge unique content from development.md → root README.md
```bash
# Manual: append troubleshooting table to README.md
```

### Step 2: Delete redundant .md files
```bash
cd /home/htzl/dgx-spark-playbooks/nvidia/multi-agent-chatbot

# Redundant docs
rm assets/README.md
rm assets/backend/README.md
rm assets/frontend/README.md
rm assets/development.md
rm assets/backend/CODE_REVIEW.md
rm assets/backend/RAG_ANALYSIS.md
rm plans/refactor_preparation_guide.md
rmdir plans/  # if empty after deletion
```

### Step 3: Delete dead frontend assets
```bash
rm assets/frontend/public/file.svg
rm assets/frontend/public/globe.svg
rm assets/frontend/public/vercel.svg
rm assets/frontend/public/window.svg
```

### Step 4: Clean build artifacts
```bash
rm -rf assets/tests/.pytest_cache/
rm -rf assets/backend/.claude/plan/
```

### Step 5: Update .gitignore files
```bash
# Root .gitignore — create or append
# assets/.gitignore — append entries from §4.2
```

### Step 6: Update CLAUDE.md Key Files section
```bash
# Edit root CLAUDE.md per §5.1
```

### Step 7: Commit
```bash
git add -A
git commit -m "chore: 删除冗余文件，收敛项目结构

- 删除 7 个冗余 .md 文件 (~2941 行)
- 删除未使用的 Next.js 默认 SVG 资源
- 清理构建缓存 (.pytest_cache)
- 更新 .gitignore 排除 Claude Code 运行时状态
- 更新 CLAUDE.md Key Files 引用"
```

---

## 8. Before/After Summary

| Metric | Before | After |
|--------|--------|-------|
| .md files | 13 | 6 |
| .md total lines | ~4332 | ~2077 |
| Dead SVG assets | 4 | 0 |
| Build artifacts tracked | 2 dirs | 0 |
| .gitignore coverage | Partial | Complete |

**Net reduction: 7 files deleted, ~2255 lines removed, zero information lost** (all findings preserved in `.claude/plans/backend-refactor.md`).

---

## 9. Relationship to Backend Refactor Plan

This cleanup is a **prerequisite** to `backend-refactor.md`:
- Removes stale references that would cause confusion during refactoring
- Establishes CLAUDE.md as the single source of truth
- Eliminates competing/contradictory architecture proposals (refactor_preparation_guide.md proposed `dto/`, `middleware/`, `common/` which conflict with CLAUDE.md's target)
- Ensures `plans/` directory is clean — only `.claude/plans/` contains active plans

Execute this plan first, then proceed with `backend-refactor.md` Phase 1.

---

## SESSION_ID (for /ccg:execute use)
- CODEX_SESSION: N/A
- GEMINI_SESSION: N/A
