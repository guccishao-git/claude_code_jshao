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
- Git user: Jason Shao <jshao@demonware.net>
- Git LFS enabled

## Preferences
- When generating daily news briefings, use the /daily-data skill
- Keep output casual and scannable — assume data engineering background
- Highlight action items in green when producing briefings
- Never include secrets, tokens, or credentials in output or commits
- If there are docs generated, by default it should be under /Documents directory. For example: /Users/jason.shao/Documents/ArsenalWeekly

After completing a task that involves tool use, provide a quick summary of the work you've done.


