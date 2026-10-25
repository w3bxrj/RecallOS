# Superpowers Core Directives

<EXTREMELY-IMPORTANT>
If you think there is even a 1% chance a skill might apply to what you are doing, you ABSOLUTELY MUST invoke the skill.
IF A SKILL APPLIES TO YOUR TASK, YOU DO NOT HAVE A CHOICE. YOU MUST USE IT.
This is not negotiable. You cannot rationalize your way out of this.
</EXTREMELY-IMPORTANT>

## The Rule
- **Invoke relevant or requested skills BEFORE any response or action** — including clarifying questions, exploring the codebase, or checking files.
- **Before entering plan mode or starting creative/feature work:** If you haven't already brainstormed, invoke the `brainstorming` skill first (`.agents/skills/brainstorming/SKILL.md`).
- Announce `"Using [skill] to [purpose]"` and follow the skill procedure exactly.

## Skill Selection & Priority
Process skills come first — they set the approach, then implementation skills carry it out:
- **Creative / New Feature / Component**: `brainstorming` first.
- **Bug fixing / Troubleshooting**: `systematic-debugging` first.
- **Planning**: `writing-plans`.
- **Plan Execution**: `executing-plans` or `subagent-driven-development`.
- **Feature Implementation**: `test-driven-development`.
- **Before claiming done**: `verification-before-completion`.
- **Review**: `requesting-code-review` / `receiving-code-review`.
- **Git workflow**: `using-git-worktrees` / `finishing-a-development-branch`.

## Antigravity CLI & IDE Equivalents
- **Dispatching subagents**: Use `invoke_subagent` (`TypeName: "self"` for full capability, `"research"` for read-only).
- **Task tracking / Checklists**: Use a task artifact via `write_to_file` (`IsArtifact: true`, `ArtifactMetadata.ArtifactType: "task"`), updating items (`- [ ]` to `- [x]`) with `replace_file_content`. Antigravity's `manage_task` tool is for background processes/jobs, not todo checklists.
