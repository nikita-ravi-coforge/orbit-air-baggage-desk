# Commands
- Activate env: source .venv/bin/activate
- Run all tests: pytest
- Run one test file: pytest tests/test_claims.py
- Lint: ruff check .

# Rules not in the code
- Deadline hours by tier: gold 4, silver 24, standard 72
- Overdue means now > deadline. Exactly at the deadline is NOT overdue.
- Rule code never reads the clock. The current time is always passed in as a parameter.
- Tests are the spec. Do not edit anything in tests/. Ask first if a test looks wrong.
- Never read or print .env.