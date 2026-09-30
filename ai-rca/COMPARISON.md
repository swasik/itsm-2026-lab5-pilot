<!-- ai-generated: 100% - Claude Code (Opus 5.5) wrote this from the two ledgers of the pilot incident of 27 September 2026; the lecturer reviews it -->

# Two investigators, one incident

Both ran the course's agent loop against the same Prometheus, with the same question, the same window
(00:38-00:50 UTC) and the same eight-step budget; only the model differed.

| | qwen3:1.7b (`ai-rca-eval.json`) | qwen3:4b-instruct (`ai-rca-eval-2.json`) |
|---|---|---|
| time to answer | 2 minutes, 6 steps | 13 minutes, 4 steps |
| tool calls that failed | 0 of 5 | 13 of 30, all range vectors sent to `query_range` |
| correct | 1 (checkout's error rate) | 0 |
| partially correct | 0 | 1 (the frontend's failing PlaceOrder, wrong mechanism) |
| hallucinated | 2 (product catalog slow, an "Order Preparation service") | 1 (flagd's EventStream errors) |
| unfalsifiable | 1 | 1 |
| found any seeded fault's cause | no | no |

Neither investigator found what the on-call found in a few minutes of reading Prometheus: payment's `Charge` failing,
shipping's quote slowed to 8.6 s, and the email service's memory growing. Both stopped at the first service whose
errors they could see - checkout for the small model, the frontend for the larger one - and called it the cause. That
is the symptom-as-cause mistake the lecture warns about: the errors surface where the user's request enters, and
the question is where they start.

Their failures differ in kind, and that is the useful part. The small model called its tools correctly but read
cumulative counters as if they were durations, and from that misreading invented slowness in a healthy service and a
service that does not exist. The larger model read what it got correctly - its "6 errors" is right, and so is its
dismissal of the ad service's single error - but 13 of its 30 tool calls failed and the rest returned raw
counters, so it reasoned from counts and filled the gaps with "might be related". A bigger model did not buy a better diagnosis here; it bought
fewer invented facts and more hedging.

What made both ledgers cheap to score is the same thing: every concrete claim became a query that either returned
something or did not, at an instant inside the incident and again on the healthy baseline. The two claims that could
not be turned into a query ("backend issues or configuration problems", "a configuration, service dependency, or
backend service outage") are the ones that sounded most like an explanation.
