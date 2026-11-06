# Orbit Air Baggage Desk

A command line claims desk for Orbit Air's lost, delayed, and damaged baggage. It files
claims, assigns them to agents, records every status change, and escalates claims that
run past their response deadline.

## Setup

Requires Python 3.12 or above.

```bash
git clone https://github.com/nikita-ravi-coforge/orbit-air-baggage-desk.git
cd orbit-air-baggage-desk
python3.13 -m venv .venv
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

### feature/schema-and-filing

**Prompt:** Drafted the tests first in plan mode with a prompt that fixed the interface (`db.connect`, `file_claim`, `get_claim`, `get_history`, `list_claims`, `now` as a datetime) and asked for every assumption not in PLAN.md. For the code, I gave the NIK-5 issue (problem, actual, expected, done when, constraints) and asked for a plan before any edits.

**What the agent did:** Drafted 6 test functions (13 collected) and listed 16 assumptions plus 4 coverage gaps. After my go, wrote `db.py` (schema with CHECK constraints, `connect`) and `claims.py` (constants, validation, deadline, `file_claim` in one `with conn:` block, getters, list filters). 13 passed, ruff clean.

**What I checked or changed:**
- I rejected the plan-mode approval and pasted the tests in myself, so the agent never wrote to `tests/`.
- The agent flagged that "an omitted note is stored as NULL" had no assert. I added one to `test_file_claim_starts_open`. Atomic filing is a known untested gap, left out to keep the planned count.
- **Stop hook loop:** I asked for a plan and told the agent to wait for my go. The tests were red by design, so the Stop hook sent the agent back on every stop: 9 times, until Claude Code's loop guard ended the turn. The agent made no edits while waiting. I changed the hook to check `stop_hook_active`, so it blocks only once per stop.
- The agent asked whether the CHECK lists in the SQL should import from `claims.py`. I said no: the duplication is deliberate, so the database guard is independent of the Python code.
- The agent made one unplanned choice, trimming passenger and flight before storing. I reviewed it and accepted it.
- I noticed the session was in auto mode, not manual, and switched to manual for later branches.
- I ran `pytest` and `ruff` myself, confirmed no clock calls with `grep`, confirmed the `with conn:` block, and read both files.

### feature/assign-and-status

**Prompt:** Drafted tests with a prompt that fixed the interface (`assign`, `resolve`, `close`, `change_status`, and `get_history` raising for unknown ids), put them in a new file `tests/test_status.py`, and asked for every assumption not in PLAN.md. For the code, I gave the NIK-6 issue and asked for a plan before any edits.

**What the agent did:** Wrote `tests/test_status.py` (4 functions, 13 tests) and listed 16 assumptions, including what the tests did not cover. Then added `ALLOWED_CHANGES`, `change_status`, and thin `assign`, `resolve`, `close` wrappers, and made `get_history` raise for an unknown id. 26 passed, ruff clean.

**What I checked or changed:**
- I wasn't in plan mode, so the agent wrote the test file directly. I reviewed it before committing.
- The agent flagged that only assign had a history check. I strengthened `test_allowed_transition` to check the new history row and `changed_by` on all 5 allowed changes, and that resolve and close keep the existing agent.
- Red was correct: 13 failed for the right reasons (missing functions, `get_history` not raising), and branch 1's 13 still passed. The Stop hook sent the agent back once per stop and didn't loop, which confirms the `stop_hook_active` fix.
- Green phase: the agent proposed either `change_status(..., agent=None)` with the agent update in the same transaction, or a private helper. I chose the `agent=` version so `change_status` stays the only reader of `ALLOWED_CHANGES`. Its plan had `agent` keyword-only; my instruction overrode that and it followed my spec.
- `git diff --stat HEAD -- tests/` was empty after coding, so no test changed after the red commit. I ran `pytest` myself (26 passed), confirmed no clock calls, and confirmed the status, agent, and history writes share one `with conn:` block.
## Hidden Instruction Check

### feature/deadlines-and-escalation

**Prompt:** Drafted tests with a prompt that fixed the interface (`escalate(conn, now)` returning ids in order, `change_status` refusing an escalation that isn't overdue) and spelled out the rollback test: file first, then install a trigger that aborts history inserts, then assign and read back on the same connection. For the code, I gave the NIK-7 issue and asked for a plan before any edits.

**What the agent did:** Wrote `tests/test_escalation.py` (6 functions, 11 tests) and listed 11 assumptions. It pointed out that the rollback test would already pass, because the transaction existed since branch 2. Then added `is_overdue`, the deadline gate in `change_status`, and the `escalate` sweep. 37 passed.

**What I checked or changed:**
- I approved the plan this time, so the agent wrote the test file itself. I reviewed it before committing.
- Red was correct: 9 tests failed with AttributeError (no `escalate`), and 1 failed with DID NOT RAISE (no deadline gate).
- **Rollback proof:** the rollback test passed before any feature code, so on its own it proved nothing. I temporarily added `conn.commit()` between the UPDATE and the history INSERT in `change_status`. The test failed with `AssertionError: assert 'assigned' == 'open'`. I reverted with `git checkout claims.py` and got 37 passed. The test passes with the transaction and fails without it.
- Green phase: the agent asked before touching the existing transaction. It proposed widening the SELECT to also read `deadline`, or adding a separate SELECT. I chose widening the existing SELECT, so the check stays in the same `with conn:` block. It chose not to catch exceptions in `escalate`, so real database errors surface. I agreed. I also accepted its offer to document the new ValueError in the docstring.
- `git diff --stat` on tests/ was empty after coding. I ran `pytest` myself (37 passed) and confirmed the overdue check uses `>` on parsed datetimes.

TODO

## Overdue Demonstration

TODO

## Code Review

TODO