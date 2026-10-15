# Scoring rubric (template)

The agent scores every job 0–100 from the **live job page** and quotes the line behind
every deduction. If the page can't be read, the job is capped and marked "not verified".
The categories and weights below are a template; my own weights came from analysing which
past applications led to interviews.

**Step 0: history.** If the same company already turned down the same or a similar role in the
last 9 months, the job is not added.

**Step 1: hard exclusions.** These are not scored, and are logged with the quoted reason:
requirements you can't meet that are stated as a MUST, the wrong location without a hybrid or
remote option, a salary below your floor, and companies with a conflict of interest.
A requirement with "or equivalent", or listed under "nice to have", is never an exclusion.

**Step 2: fit points (max 100)**

| | Category | Points |
|---|---|---|
| A | Role family: how close the role is to what you do best | 0–30 |
| B | Domain: industries where your background counts | 0–20 |
| C | Requirement match: starts at 25; deduct only for quoted MUST lines (skills, years gap, certifications) | 0–25 |
| D | Work style: the mix you want (for example internal vs client-facing) | 0–10 |
| E | Company type: stage and size, direct employer vs agency hiding the client | 0–10 |
| F | Logistics: location and hybrid days stated; temporary contracts penalised | 0–5 |
| G | Bonus: the role asks for something you are unusually strong in | +5 |

Each job's breakdown is saved with it, e.g. `[A30 B20 C21 D10 E10 F3 G5=99]`.

**Priority (0–10)** decides what to act on first among jobs with equal scores:
a named contact at the company, a named recruiter, applying through the company's own site,
how recently the job was posted, and how many people have applied so far.
