# Charli3 Project Governance

Charli3 provides decentralized oracle infrastructure for Cardano. This document
explains how the project is governed, how decisions are made, and how contributors
can take on greater responsibility.

- [Values](#values)
- [Maintainers](#maintainers)
- [Becoming a Maintainer](#becoming-a-maintainer)
- [Removing a Maintainer](#removing-a-maintainer)
- [Meetings](#meetings)
- [Code of Conduct Enforcement](#code-of-conduct-enforcement)
- [Security Response](#security-response)
- [Voting](#voting)
- [Modifying this Charter](#modifying-this-charter)

## Values

The Charli3 project embraces the following values:

- **Openness:** Communication and decision-making happens in the open and is
  discoverable for future reference. All discussions and work take place in
  public forums and open repositories wherever possible.
- **Fairness:** All stakeholders have the opportunity to provide feedback and
  submit contributions, which will be considered on their merits.
- **Community over company:** Sustaining and growing the community takes
  priority over shipping code or any single sponsor's goals. Each contributor
  participates as an individual.
- **Inclusivity:** We innovate through different perspectives and skill sets,
  which can only be accomplished in a welcoming and respectful environment.
- **Participation:** Responsibilities within the project are earned through
  participation, and there is a clear path from contributor to maintainer.

## Maintainers

Maintainers have write access to Charli3 repositories under the
[Charli3-Official](https://github.com/Charli3-Official) organisation. The
current list of maintainers is kept in
[MAINTAINERS.md](./MAINTAINERS.md).

Maintainers are people who care about the project and want to help it grow.
A maintainer is not just someone who can merge changes, but someone who has
demonstrated the ability to collaborate with the team, produce high-quality
code or documentation, and follow through to fix issues.

The collective team of all Maintainers is known as the **Maintainer Council**,
which is the governing body for the project.

## Becoming a Maintainer

To be proposed as a maintainer you should demonstrate:

- Sustained participation in discussions, contributions, and code or
  documentation reviews over a meaningful period.
- Several non-trivial pull requests merged across one or more repositories.
- Reviews completed for non-trivial pull requests by others.
- Understanding of the project's architecture, coding style, and review
  process.
- Ability to collaborate constructively with the existing team.

An existing maintainer proposes the candidate by opening an issue or
discussion in the relevant repository. A simple majority vote of existing
maintainers approves the nomination. Nominations are evaluated without
prejudice to employer or demographics.

Once approved, the new maintainer is granted the necessary GitHub permissions
and added to MAINTAINERS.md.

## Removing a Maintainer

Maintainers may resign at any time by notifying the Maintainer Council.

Maintainers may also be removed for inactivity (no meaningful activity for
12 months with no stated return date), failure to fulfil maintainer
responsibilities, or violation of the Code of Conduct. Removal requires a
two-thirds vote of the remaining maintainers.

A removed maintainer may be granted Emeritus status, where they retain
informal advisory standing and can be reinstated quickly if their
availability changes.

## Meetings

The Maintainer Council meets as needed. Security issues and Code of Conduct
reports may trigger closed meetings; all current maintainers must be
invited to such meetings except any maintainer who is the subject of a
report.

Community questions and technical discussion take place in:
- [Discord](https://discord.gg/Tnsc3HCA3A)

## Code of Conduct Enforcement

Code of Conduct violations are reported to **info@charli3.io** and handled
by the Maintainer Council in accordance with the
[Code of Conduct](./CODE_OF_CONDUCT.md). If a maintainer is directly
involved in a report, the remaining maintainers will manage the process
without that individual.

## Security Response

The Maintainer Council is responsible for handling security reports in
accordance with the [Security Policy](./SECURITY.md). At least two
maintainers must be involved in reviewing any security report. The Security
Response team is reviewed at least annually.

To report a vulnerability, follow the instructions in
[SECURITY.md](./SECURITY.md) — **do not open a public issue**.

## Voting

Most project business is conducted by
[lazy consensus](https://community.apache.org/committers/lazyConsensus.html).
When a formal vote is needed, it is taken via GitHub issue or pull request
comments using `+1` (approve), `0` (abstain), or `-1` (disapprove) notation.

- Simple majority of all maintainers is required for most decisions.
- A two-thirds majority is required for: maintainer removal, changes to this
  governance document, and major architectural decisions.

Votes should remain open for at least five business days to allow all time
zones to participate.

## Modifying this Charter

Changes to this governance document require a two-thirds vote of the
Maintainer Council and must be made via pull request with at least one week
open for community comment before merging.
