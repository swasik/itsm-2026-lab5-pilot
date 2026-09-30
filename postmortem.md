---
lab4_postmortem:
  ticket: be17ddf2-2d48-49e2-ac37-e1e26f8f1ac2
  detecting_alert: ShopCheckoutErrors
  onset: 2026-09-27T00:45:35Z
  detection: 2026-09-27T00:48:09Z
  acknowledgement: 2026-09-27T00:49:26Z
  recovery: 2026-09-27T00:56:09Z
  mttd_seconds: 154
  mtta_seconds: 77
  mttr_seconds: 634
  identified_flags: [paymentFailure, intlShippingSlowdown, emailMemoryLeak]
---
<!-- ai-generated: 100% - Claude Code (Opus 5.5) wrote this from the course team's pilot incident of 27 September 2026 (the reference run of design/LAB4.md); the lecturer reviews it -->

# Postmortem: checkout failing for one order in five

## Date

2026-09-27, 00:45:35 to 00:56:09 UTC (10 minutes 34 seconds of customer impact).

## Authors

The course team's on-call for the Lab 4 pilot (reference implementation of `svcdesk`, login `itsm-reference`).

## Status

Complete. The fault is mitigated, the action items are open, and the problem record below stays open until the
first two action items are done.

## Summary

For ten and a half minutes about 19 % of the shop's orders failed at payment, international shipping quotes took up
to 8.6 s instead of 4 ms, and the email service leaked memory. Three feature flags had been switched on together by
the course's fault injector. `ShopCheckoutErrors` paged 2 minutes 34 seconds after the onset; the on-call switched
the three flags off 6 minutes 26 seconds after the onset and the page resolved 4 minutes later.

## Impact

Between 00:45:35 and 00:52:03 about 19 % of `PlaceOrder` calls failed (18.6 % of checkout's server spans at 00:49,
over 5 minutes; the baseline has none), so roughly one customer in five who tried to pay was refused. Orders that did
succeed were slow: checkout's p99 reached 9.25 s because the shipping quote inside it took up to 8.6 s (p99, against
3.6 ms on the baseline). Browsing, the cart and the product catalog were not affected - the product catalog's p99
stayed at 8 ms throughout. No data was lost; failed orders were not charged.

## Root Causes

Three flags of the demo's feature-flag service were on at once, one from each class of the injector's pool:
`paymentFailure` (the payment service rejects a share of `Charge` calls, visible as `STATUS_CODE_ERROR` on payment's
and checkout's server spans: 19.2 % and 18.6 % at 00:49), `intlShippingSlowdown` (the shipping service delays its
quote, visible as shipping's p99 of 8,625 ms against 3.6 ms) and `emailMemoryLeak` (the email service retains memory
on every confirmation, visible as its container growing from 60 MB at the onset to 84 MB at 00:52). The shop has no
control that stops a flag change from reaching production traffic at full strength, and no alert tells anyone that a
flag changed.

## Trigger

The course's fault injector, armed at 00:41:55, switched the three flags on at 00:45:35 - the moment
`seeded_fault_active` appears in the TSDB. In a real shop this is the deploy-free change that nobody reviews: a flag
flipped in a console.

## Resolution

The on-call switched the three flags off through the injector, one after another, at 00:52:01, 00:52:02 and
00:52:03 (`POST /flags/<flag>/off`). Errors stopped at the next export of the span metrics; `ShopCheckoutErrors`
resolved at 00:56:09 because its 5-minute window needed four minutes to forget the failures. The ticket was moved to
in progress and resolved at 00:56:30.

## Detection

`ShopCheckoutErrors` (P1: more than 5 % of checkout's server spans failing over 5 minutes, `for: 1m`) went pending at
00:47:09 and fired at 00:48:09; Alertmanager paged at 00:48:19 after its 10 s `group_wait`. The two P2 warnings that
fired with it - `ShopServiceErrors` for checkout and payment and `ShopServiceSlow` for checkout and shipping - were
inhibited by the P1 and reached nobody, as designed. Of the 154 s to detection, about 60 s is the collector's export
interval (span metrics arrive once a minute), up to 60 s the 1-minute `for`, and the rest the 5-minute rate window
filling.

## Action Items

| Action Item | Type | Owner | Bug |
|---|---|---|---|
| Alert on any flag change of the shop's flag service, as a P3 to chat, with the flag's name | prevent | on-call | ITSM-41 |
| Put the payment and shipping flags behind a percentage rollout that starts at 1 % | prevent | shop team | ITSM-42 |
| Page on checkout latency too: `ShopCheckoutSlow`, P1, p99 above 3 s for 2 minutes (done 27 September) | prevent | on-call | ITSM-46 |
| Add a 2-minute error-ratio alert next to the 5-minute one, so recovery is visible sooner | mitigate | on-call | ITSM-43 |
| Add a memory-growth alert per container (P2), which the email leak would have tripped | mitigate | on-call | ITSM-44 |
| Write the "switch the last flags off first" step into the checkout runbook | process | service desk | ITSM-45 |

## Lessons Learned

### What went well

The P1 paged once and only once: the inhibition kept four P2 warnings off the chat channel while checkout was the
real problem. The ticket was opened 27 s after the page and acknowledged 40 s later, well inside the P1 SLA.

### What went wrong

Detection took 154 s, most of it the metrics pipeline rather than the rule. The AI investigator (qwen3:1.7b through the
course's MCP server) spent its budget on raw counters, read counts as durations, and blamed the product catalog, which
was healthy; nothing it said could be used without checking. Recovery looked 4 minutes slower than it was because the
alert's window is 5 minutes.

### Where we got lucky

The memory leak was the slowest of the three faults: 24 MB in six minutes would have taken the email service down
only much later, so switching it off with the other two cost nothing. Had it been the one flag we missed, nothing
would have paged at all. And the payment errors paged for all three faults: the shipping slowdown alone - checkout's
p99 at 9.2 s - would have paged no one, because our only P1 watched errors and `ShopServiceSlow` is a P2; hence
the `ShopCheckoutSlow` action item.

## Timeline

2026-09-27, all times UTC.

| time | event |
|---|---|
| 00:31:52 | The fault injector starts; the 10-minute baseline begins. No P1 fires during it. |
| 00:41:55 | The injector is armed (`POST /arm`). |
| 00:45:35 | **Onset**: `paymentFailure`, `intlShippingSlowdown` and `emailMemoryLeak` switch on. |
| 00:46:09 | `ShopServiceSlow` pending for checkout and shipping. |
| 00:47:09 | `ShopCheckoutErrors` pending. |
| 00:48:09 | **Detection**: `ShopCheckoutErrors` firing. |
| 00:48:19 | The pager receives the page. |
| 00:48:46 | P1 ticket `be17ddf2-2d48-49e2-ac37-e1e26f8f1ac2` opened. |
| 00:49:00 | The AI investigator is started on the window 00:38-00:50; it answers at 00:51:02 (`ai-rca/transcript.md`). |
| 00:49:26 | **Acknowledgement** of the ticket. |
| 00:49-00:51 | The on-call reads Prometheus: payment and checkout errors at 19 %, checkout p99 9.2 s, shipping p99 8.6 s, email memory rising - three symptoms that match three flags of the published pool, one per class. |
| 00:52:01 | `paymentFailure` switched off; `intlShippingSlowdown` at 00:52:02, `emailMemoryLeak` at 00:52:03. |
| 00:53:59 | `ShopServiceSlow` resolves. |
| 00:56:09 | **Recovery**: `ShopCheckoutErrors` resolves; the pager gets the resolved notification at 00:56:19. |
| 00:56:30 | Ticket resolved. |

## Supporting information

The TSDB snapshot is `incident/tsdb-snapshot.tar.gz` and the ticket `incident/ticket.json`; `itsmlab incident 4`
recomputes onset 00:45:35, detection 00:48:09, acknowledgement 00:49:26 and recovery 00:56:09 from them. The queries
behind the numbers above are the `predicts` of `ai-rca-eval.json` plus shipping's
`histogram_quantile(0.99, sum by (le) (rate(traces_span_metrics_duration_milliseconds_bucket{service_name="shipping",
span_kind="SPAN_KIND_SERVER"}[5m])))` and `container_memory_usage_total_bytes{container_name="email"}`.

## Problem record

Incident record: be17ddf2-2d48-49e2-ac37-e1e26f8f1ac2 (P1, resolved 00:56:30).

Root cause: three feature flags switched on together at full strength with no rollout and no alert on flag changes.

Known error: a flag change reaches all production traffic at once and is visible only through its symptoms.

Workaround: switch the flags of the payment, shipping and email services off through the flag service and watch the
checkout error ratio fall below 5 %.
