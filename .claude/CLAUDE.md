# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) across all sessions.

## About Me
- Project manager in the Acitvision Data department
- Primary tools: Databricks (GCP), Apache Airflow, Jira, Airbyte
- Databricks workspace: GCP region, profiles configured in ~/.databrickscfg (prefer `jshao` or `Unity` profiles with CLI auth)

## Environment
- macOS, shell: zsh
- Homebrew at /opt/homebrew/bin
- Python via Homebrew (`/opt/homebrew/bin/python3`)
- Databricks CLI and gcloud SDK installed
- Git user: 
- Git LFS enabled

## Preferences
- When generating daily news briefings, use the /daily-data skill
- Keep output casual and scannable — assume data engineering background
- Highlight action items in green when producing briefings
- Never include secrets, tokens, or credentials in output or commits
- All the skills must be under /Users/jason.shao/Documents/GitHub1/claude_code_jshao/.claude/commands
- If there are docs generated, by default it should be under /Documents directory. For example: /Users/jason.shao/Documents/ArsenalWeekly

After completing a task that involves tool use, provide a quick summary of the work you've done.

## Communication Style
When the user asks for a quick opinion or confirmation, keep it brief. Do not provide unsolicited detailed feedback or analysis unless asked.

## HTML Slides Generation
When generating or fixing HTML slide decks, always verify: (1) nav dots JS is included, (2) no leaked model reasoning in output, (3) consistent fonts via body-level CSS, (4) all slides render without overflow. Apply fixes globally, not slide-by-slide.

## Skills & Commands
- When asked to run a skill or command, execute it directly — do not edit the underlying template/prompt files unless explicitly asked to modify the skill itself.


