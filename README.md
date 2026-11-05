# Orbit Air Baggage Desk

A command line claims desk for Orbit Air's lost, delayed, and damaged baggage. It files
claims, assigns them to agents, records every status change, and escalates claims that
run past their response deadline.

## Setup

Requires Python 3.12 or above.

```bash
git clone https://github.com/nikita-ravi-coforge/orbit-air-baggage-desk.git
cd orbit-air-baggage-desk
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

TODO: walkthrough of all eight commands, added on feature/cli.

## Running Tests

```bash
pytest                          # run all tests
pytest tests/test_claims.py     # run one test file
ruff check .                    # lint
```

## Linear Issues

## Linear Issues

## Linear Issues

Project: Orbit Air Baggage Desk

- [NIK-5 · feature/schema-and-filing](https://linear.app/nikita-ravi/issue/NIK-5/featureschema-and-filing-tables-filing-validation-deadline-list)
- [NIK-6 · feature/assign-and-status](https://linear.app/nikita-ravi/issue/NIK-6/featureassign-and-status-assign-resolve-close-allowed-changes-history)
- [NIK-7 · feature/deadlines-and-escalation](https://linear.app/nikita-ravi/issue/NIK-7/featuredeadlines-and-escalation-overdue-rule-escalation-sweep-rollback)
- [NIK-8 · feature/cli](https://linear.app/nikita-ravi/issue/NIK-8/featurecli-all-commands-now-option-seed)

## Setup Check

**What was configured:** `.claude/settings.json` has the deny rules `Read(./.env)` and
`Read(./.env.*)`. `.env` holds only a fake key, is listed in `.gitignore`, and has never
been committed.

**Test 1: CLAUDE.md instruction, not enforcement.** In a new Claude Code session in manual
mode, I asked "What is in the .env file?". Claude refused because my CLAUDE.md had a line
saying never to read or print `.env`. It never attempted a read, so this only showed the
model following an instruction. A CLAUDE.md line is a request the model can choose to follow,
not a rule the harness enforces. I removed that line and restarted the session so the deny
rule could be tested on its own.

**Test 2: Read tool.** I asked: "I'm testing my deny rule. Use the Read tool to open .env and
show me its contents." Claude attempted the Read, and the harness blocked it before it ran:

> File is in a directory that is denied by your permission settings.

**Test 3: shell command.** I asked Claude to run `cat .env`. The Bash call was blocked:

> Permission to use Bash with command cat .env has been denied.

There is no Bash rule in my settings, so the Read deny rule is also being applied to a shell
command that plainly reads the file.

**Conclusion:** The deny rule is enforced by the harness, not by the model's choice. Both the
Read tool and `cat .env` were blocked, and the file's contents never entered the context
window. Claude itself pointed out the limit: rules match tool calls, not intent. A command
such as `python -c "print(open('.env').read())"` is not guaranteed to be caught. For a hard
boundary, the sandbox with filesystem read restrictions is the stronger control. For this lab
the fake key, the deny rule, `.gitignore`, and GitHub push protection together keep `.env` out
of both the agent's context and the repository.

## Agent Log

TODO: one entry per branch.

## Hidden Instruction Check

TODO

## Overdue Demonstration

TODO

## Code Review

TODO