---
title: "Project Kickoff Brief"
description: "Create a structured project kickoff document with scope, goals, timeline, and RACI."
tags: [operations, project, planning, kickoff]
version: 1
created: "2026-04-08"
---

# Project Kickoff Brief

Create a clear project brief that aligns all stakeholders on scope, goals, and responsibilities.

## When to use

- User is starting a new project or initiative
- User says "project kickoff", "project brief", "project plan"
- User needs to align a team on what, why, and how

## Steps

1. **Define the project**:
   - **Name**: Short, memorable
   - **Sponsor**: Who owns the budget and decision authority?
   - **Problem statement**: What problem are we solving? (1-2 sentences, specific)
   - **Success criteria**: How do we know we succeeded? (measurable)

2. **Set scope**:
   - **In scope**: Specific deliverables and features
   - **Out of scope**: What we explicitly WON'T do (prevents scope creep)
   - **Dependencies**: What do we need from others?
   - **Assumptions**: What are we taking for granted?

3. **Timeline and milestones**:
   - Break into phases with dates
   - Identify major milestones and decision gates
   - Include buffer (15-20%)

4. **Build RACI matrix**:
   | Task | Responsible | Accountable | Consulted | Informed |
   |---|---|---|---|---|
   For each major deliverable, assign roles.

5. **Identify risks**: Top 3-5 risks with mitigation plans (reference risk-assessment skill for deeper analysis).

6. **Define communication cadence**: Standups, status reports, reviews.

7. **Save**: `wiki/synthesis/kickoff-[project].md`

## Output format

```markdown
# Project Kickoff: [Project Name]

## Overview
- **Sponsor**: [Name]
- **Lead**: [Name]
- **Start date**: [Date]
- **Target completion**: [Date]
- **Status**: Planning / In Progress / Complete

## Problem Statement
[What problem are we solving? Why now?]

## Goals & Success Criteria
| Goal | Metric | Target |
|---|---|---|
| ... | ... | ... |

## Scope
### In Scope
- [Deliverable 1]
- [Deliverable 2]

### Out of Scope
- [Explicitly excluded item 1]
- [Explicitly excluded item 2]

### Assumptions
- [Assumption 1]

### Dependencies
- [Dependency 1]: [Owner, expected by date]

## Timeline
| Phase | Duration | Milestone | Date |
|---|---|---|---|
| Discovery | 2 weeks | Requirements signed off | [Date] |
| Build | 4 weeks | Beta ready | [Date] |
| Launch | 1 week | Go-live | [Date] |

## RACI Matrix
| Deliverable | Responsible | Accountable | Consulted | Informed |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| ... | ... | ... | ... |

## Communication
| Meeting | Frequency | Participants | Purpose |
|---|---|---|---|
| Standup | Daily | Team | Progress & blockers |
| Status update | Weekly | Stakeholders | Progress report |
| Review | Bi-weekly | Sponsor | Decision gate |
```

## Pitfalls

- A kickoff without defined "out of scope" guarantees scope creep
- Don't skip the RACI — unclear ownership is the #1 project killer
- Success criteria must be measurable — "improve quality" is not a criterion
- The kickoff brief is a living document — update it when scope changes (and get sign-off)
