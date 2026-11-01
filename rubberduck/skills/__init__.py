"""Intent-behavior misalignment checks for agent skills.

A skill is a folder with declarative files (SKILL.md, README, other docs) that
say what it does, and executable files (scripts, inline code) that decide what
it actually does. This package reads both sides, collects static facts about
the code, and asks one model call whether the two sides agree.
"""
