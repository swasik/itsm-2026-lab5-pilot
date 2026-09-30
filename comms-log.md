---
lab4_comms:
  awareness: 2026-09-27T00:49:26Z          # NIS2 "becoming aware": a person acknowledged the page
  detection: 2026-09-27T00:48:09Z          # KSC "od momentu jego wykrycia": the P1 alert fired
  classification: 2026-09-27T01:30:00Z     # DORA: the payment institution classifies it as major
  nis2:
    early_warning_sent: 2026-09-27T09:00:00Z
    early_warning_due: 2026-09-28T00:49:26Z
    notification_sent: 2026-09-28T14:00:00Z
    notification_due: 2026-09-30T00:49:26Z
    final_report_due: 2026-10-28T14:00:00Z
  ksc:
    early_warning_sent: 2026-09-27T09:00:00Z
    early_warning_due: 2026-09-28T00:48:09Z
    notification_sent: 2026-09-28T14:00:00Z
    notification_due: 2026-09-30T00:48:09Z
    final_report_due: 2026-10-28T14:00:00Z
  dora:
    initial_sent: 2026-09-27T04:30:00Z
    initial_due: 2026-09-27T05:30:00Z
    intermediate_sent: 2026-09-29T16:00:00Z
    intermediate_due: 2026-09-30T04:30:00Z
    final_due: 2026-10-29T16:00:00Z
  log:
    - {at: 2026-09-27T00:49:40Z, to: "#shop-incident (internal chat)", what: "P1 acknowledged: about one order in five fails at payment; investigating"}
    - {at: 2026-09-27T00:53:00Z, to: "status page", what: "Degraded: some payments fail; a mitigation is applied and errors are falling"}
    - {at: 2026-09-27T00:57:00Z, to: "status page", what: "Resolved at 00:56 UTC; failed orders were not charged and can be placed again"}
    - {at: 2026-09-27T04:30:00Z, to: "KNF (DORA initial notification, by the payment institution)", what: "major ICT-related incident: payment failures 00:45-00:52 UTC, 19 % of transactions"}
    - {at: 2026-09-27T09:00:00Z, to: "CSIRT sektorowy (early warning, NIS2 and KSC)", what: "significant incident, not suspected to be malicious, no cross-border impact"}
    - {at: 2026-09-28T14:00:00Z, to: "CSIRT sektorowy (incident notification, NIS2 and KSC)", what: "initial assessment: severity, impact, three flags switched on together; no indicators of compromise"}
    - {at: 2026-09-29T16:00:00Z, to: "KNF (DORA intermediate report)", what: "root cause and the prevent actions of the postmortem"}
---
<!-- ai-generated: 100% - Claude Code (Opus 5.5) wrote this from the pilot incident of 27 September 2026 and Lecture 4 FACTS N-02, N-06, N-11; the lecturer reviews it -->

# Communications and the regulators' clocks

## The assumption this log rests on

The exercise asks which clocks would run if the incident were reportable. We treat the shop as an important entity
under NIS2 (a provider of an online marketplace, Annex II) and so under the amended KSC act, and its payment service as
run by our subsidiary, a payment institution and so a financial entity under DORA. Honestly assessed, ten minutes
in which one payment in five failed and nobody was charged would probably not be a significant incident under NIS2
Art. 23(3) nor a major one under DORA's classification criteria. The log shows the clocks as if it were, because that
is the part of the job the three regimes make hard: three clocks, three different starting instants, two recipients.

## The three starting instants, defended

- **Awareness (NIS2): 00:49:26**, when the on-call acknowledged the page. The alert at 00:48:09 was a machine's
  detection; the entity becomes aware when a person has seen it and knows what it is looking at. Choosing the later
  instant is not a loophole: the acknowledgement came 77 s after the alert, and the ticket records who and when.
- **Detection (KSC): 00:48:09**, when `ShopCheckoutErrors` fired. The Polish act counts "od momentu jego wykrycia", from
  detection, not awareness, so its clock starts 77 s earlier than NIS2's for the same incident.
- **Classification (DORA): 01:30:00**, when the payment institution applied its classification criteria to the
  postmortem's numbers (clients affected, duration, the payment service being critical) and called it major. Classified
  within 24 h of awareness, the initial report is due at the earlier of classification + 4 h (05:30) and awareness +
  24 h (00:49:26 on 28 September): 05:30.

## The deadlines

| regime | report | runs from | due | sent |
|---|---|---|---|---|
| NIS2 | early warning | awareness + 24 h | 2026-09-28 00:49:26 | 2026-09-27 09:00 |
| NIS2 | incident notification | awareness + 72 h | 2026-09-30 00:49:26 | 2026-09-28 14:00 |
| NIS2 | final report | notification + 1 month | 2026-10-28 14:00 | - |
| KSC | wczesne ostrzeżenie | detection + 24 h | 2026-09-28 00:48:09 | 2026-09-27 09:00 |
| KSC | zgłoszenie incydentu poważnego | detection + 72 h | 2026-09-30 00:48:09 | 2026-09-28 14:00 |
| KSC | sprawozdanie końcowe | notification + 1 month | 2026-10-28 14:00 | - |
| DORA | initial notification | min(classification + 4 h, awareness + 24 h) | 2026-09-27 05:30 | 2026-09-27 04:30 |
| DORA | intermediate report | initial sent + 72 h | 2026-09-30 04:30 | 2026-09-29 16:00 |
| DORA | final report | intermediate sent + 1 month | 2026-10-29 16:00 | - |

The NIS2 and KSC reports go to the same recipient, the sector CSIRT, in one submission each, which is why they were
sent together: the KSC deadlines are 77 s earlier and bind first. The final reports' clocks start at the submissions,
not at the incident, so sending the notification early moves the final report earlier too - a trade-off, not a free
win. DORA's weekend relief (RTS Art. 5(4)) is ignored here, as the handout says.
