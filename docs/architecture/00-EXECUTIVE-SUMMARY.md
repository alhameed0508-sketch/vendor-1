# MuleCatch — Executive Summary

**Reading time: under 10 minutes. No prior technical knowledge assumed.**

---

## What MuleCatch is

MuleCatch is a software platform that identifies bank accounts being used to receive and move the
proceeds of fraud, known as money mule accounts. It examines transactions, account behaviour and the
relationships between accounts, then produces a prioritised list of suspected networks for a human
investigator to review. Every item it produces carries a plain-language explanation of why it was
flagged, so that an investigator and their supervisor can judge the case themselves rather than accept
a machine verdict.

---

## The problem it addresses

When a customer is defrauded, the money does not stay still. It is moved through a chain of accounts,
often within minutes, then withdrawn. The accounts in that chain belong to money mules. Some are
willing participants. Many are ordinary people recruited under false pretences, which matters because
the bank's correct response to each is different.

Three features of Indian digital payments make these accounts hard to find. Payments settle in seconds
and run around the clock, so funds received overnight can be gone before any daily review takes place.
Volumes are very high, which means any detection method producing too many false alarms is unusable
regardless of how clever it is, because investigator time is finite. And most importantly, a single
mule account usually looks unremarkable on its own. Modest balances, plausible counterparties, no
obvious threshold breaches. The pattern only becomes visible when you look at the relationships
between many accounts at once.

Conventional monitoring sets fixed rules and thresholds. That approach struggles here for a simple
reason: the thresholds are widely known, so they are easy to stay beneath, and they examine each
account in isolation, so they cannot see a coordinated group. MuleCatch's answer is to look at the
same activity from several independent angles at the same time, including the relationships between
accounts, so that avoiding one angle does not mean avoiding detection.

---

## What is genuinely different about it

The platform's real distinguishing feature is that it produces **one investigable case for a whole
network**, and that case arrives with its evidence already assembled.

A conventional system alerts on individual accounts. An investigator receiving thirty separate alerts
must work out for themselves that they are one operation, which accounts matter most, and what the
connection is. MuleCatch identifies the group as a group, and presents it with the transaction
network, the timing pattern, the shared devices, the behavioural changes, and a written summary of
what it believes is happening and why.

This matters operationally rather than academically. It changes the investigator's task from
reconstruction to judgement, which is a better use of scarce expert time. It also matters for
regulatory reasons: an adverse decision affecting a customer must be explicable, a supervisor
approving a report to the authorities is accepting personal responsibility for it, and an examiner may
ask months later why a particular account was reported. All three require the reasoning to be
recorded and legible, not just the conclusion.

This capability is substantially built. The network detection works and is tested. The reasoning is
generated and stored.

---

## Readiness posture

Four labels are used throughout the technical documents. **Validated** means it works and is properly
tested. **Integrated** means it works and is connected to the live system. **Implemented** means the
code exists but nothing in the running product reaches it. **Planned** means it does not exist yet.

| Capability area | Status | Evidence in one line |
|---|---|---|
| Transaction monitoring | Validated | Seven analytic layers, all reachable and tested |
| Network and graph analysis | Validated | Community detection works and is the platform's strongest layer |
| Behavioural profiling | Validated | Substantial genuine test coverage |
| Investigator workflow | Integrated | Triage, review, notes and escalation all work |
| Regulatory report preparation | Integrated | Full approval workflow with role controls |
| Onboarding risk assessment | Integrated, **impaired** | One of its checks silently returns nothing |
| Explainability | Integrated, **partly undelivered** | Three of seven explanation outputs do not reach the screen |
| Security controls | Integrated, **with gaps** | Real access control, but authentication is off by default outside production |
| Regulatory transmission | **Simulated** | No report is actually sent anywhere |
| India-specific signals | **Implemented only** | Built, tested, and not connected to the running product |
| Continuous learning | **Implemented only** | Investigator feedback is collected but never acted upon |
| Model validation | **Absent** | No accuracy measurement on real bank data exists |
| Backup and recovery | **Absent** | The database holding all reports has no backup |

---

## What is not production-approved

This section is deliberately placed before the positives that follow it, because these points should
not be discovered late.

**No accuracy figure on real data exists.** Every performance number in the project comes from
artificially generated test data. The one real bank file supplied has no confirmed answers attached to
it, so no accuracy could be calculated from it, and the system correctly reports that. On the
artificial data the results are also unstable: in half of the ten formal test runs the system found
nothing at all, and two runs configured identically produced results differing by a factor of nearly
two. Any single impressive figure quoted from these tests would be misleading.

**Two widely repeated figures are not measurements.** The claim of a 75 percent reduction in
investigation time originates as a default value in a database column and is displayed on a dashboard
as though it were an outcome. The claim of a 40 percent reduction in false alarms has no supporting
measurement. Both should be treated as hypotheses.

**No report is actually filed.** The workflow for preparing, approving and submitting a suspicious
transaction report is real and works. The submission step does not contact the financial intelligence
unit. It generates a reference number locally and records the report as submitted. The system contains
no address, credential or certificate for the reporting portal, so this is not a configuration matter.
To the project's credit, the code and existing documentation both say so plainly.

**The record of who approved a report cannot be trusted.** The approval step correctly requires a
supervisor. But the identity written into the record is a fixed placeholder value rather than the
person who actually approved it, and none of the report workflow is covered by the system's
tamper-evident audit log. For a regulated filing this is the most serious single issue in the
platform.

**Authentication is switched off by default** in any environment not explicitly named "production",
and when off, every user is treated as an administrator. That includes exactly the pilot and test
environments where a bank would first place real customer data.

**About a third of the codebase is not reachable** from the running product. This includes the entire
set of India-specific detection signals and the alert prioritisation model. These are built and tested
in isolation, but nothing in the live system calls them.

**Neither the audit log nor any report has a backup.** The database holding both has no backup
process, and the one backup script that exists has nothing scheduled to run it. No recovery has ever
been tested.

---

## The path to a pilot

The encouraging finding from the technical review is how little of this is structural. The
architecture is sound. Most of the problems are things that were built and then not connected, or two
pieces of software disagreeing about a name.

**Eight of the defects are single-line changes.** Between them they restore three broken features
visible to investigators, close a security exposure, make a failing security check actually block a
release, and remove a defect that makes detection results depend on which server handled the traffic.

**A further short list of small changes** would make the filing record trustworthy: record the real
approver, cover the report workflow in the audit log, and allow an approval made in error to be
withdrawn, which is currently impossible.

**Then two things the bank must supply, which no amount of software work can substitute for.** First,
historical data with confirmed outcomes attached, so the system's accuracy can actually be measured
and its thresholds set deliberately rather than by expert guess. Second, a period of running the
system alongside the existing one without acting on its output, to compare alert volumes before
anything is trusted. The platform currently has no mode for doing that, and adding one is a small
piece of work and a sensible prerequisite.

Beyond that sit the items only the institution can provide: reporting credentials and acceptance
testing with the financial intelligence unit, integration with the bank's identity systems,
penetration testing, a tested recovery process, and formal sign-off from legal, compliance, security
and model risk. These are listed with the evidence each requires in the delta register.

---

## Verdict

MuleCatch is a well-architected and unusually complete detection platform. Its central idea, that
mule activity is a network phenomenon and should be investigated as one, is correct and is genuinely
implemented. The commitment to explaining every decision is real and is the right instinct for a
regulated environment.

It is not yet a production anti-money-laundering control. Its scoring has never been calibrated
against real outcomes, its regulatory filing is simulated, its record of who approved a filing is not
trustworthy, and a material part of what it contains is not connected to what it runs.

The fair summary is: **strong architecture, incomplete integration, absent validation.** It is a
credible candidate for a controlled pilot once the integration defects are closed and real-data
evaluation has been done. It is not yet suitable for making decisions that affect customers.

---

**For detail:** the complete gap list with severity and ownership is in
[11-DELTA-REGISTER.md](11-DELTA-REGISTER.md). The full end-to-end architecture is in
[12-END-TO-END-ARCHITECTURE.md](12-END-TO-END-ARCHITECTURE.md). Start at [README.md](README.md) for a
reading path suited to your role.

*Engineering readiness is not regulatory approval. Nothing in this document set constitutes a
compliance opinion.*
