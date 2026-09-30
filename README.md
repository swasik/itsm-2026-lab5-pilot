<!-- ai-generated: 100% - Claude Code (Fable 5.1) wrote this file while building and running the reference; every command below was executed once on 12 September 2026 -->
# svcdesk reference implementation (Labs 1-4)

The reference solution of Lab 1 of the ITSM course (WSB Merito, 2026/27): a service-desk HTTP/JSON API with a
priority matrix, two SLA clocks, breach and pause semantics, a ticket state machine and a per-request test clock,
exactly as `design/LAB1.md` section 1 specifies. It serves three purposes:

1. the **test oracle** of the Tier A checker (`itsm/2026/checker/`): the checker's SLA arithmetic and this
   implementation are written independently and cross-check each other;
2. the **starting checkpoint of Lab 2**: after the Lab 1 correction window closes, this tree becomes the tag
   `checkpoint/lab-1` of the course template (see "How it becomes checkpoint/lab-1");
3. a **complete example submission**: it carries every artifact the checker reads (`DECISIONS.md`,
   `docker-compose.yml`, the `tests` profile, `specs/`, `CLAUDE.md`, `.claude/agents/reviewer.md`,
   `AGENT-POLICY.md`, `itsmlab.yaml`, AI-disclosure headers).

Students never see this directory until the checkpoint is published.

## Prerequisites

- Python 3.13 through `uv` (`uv venv --python 3.13` downloads it if needed; no global installs).
- Docker with the Compose plugin (built and verified with Docker 29.5 and Compose v5.1; anything with
  `docker compose` v2.24 or newer works). The image needs the network once, at build time.
- `curl` for the examples below.

All commands run from this directory:

```bash
cd itsm/2026/grader/reference/svcdesk
```

## Layout

```
README.md                  this file
DECISIONS.md               the decision record for the shipped defaults (generated, see below)
make_decisions.py          writes DECISIONS.md for any of the eight combinations
docker-compose.yml         the compose contract: service svcdesk on 8080, tests service under profile "tests"
Dockerfile                 python:3.13-slim, dependencies installed at build time, non-root, no network at run time
pyproject.toml             package metadata, pinned dependencies, pytest configuration
itsmlab.yaml               lab, baselines, repository names, checker image
CLAUDE.md                  instructions for coding agents working on this repository
AGENT-POLICY.md            blast-radius justification of every tool the reviewer sub-agent is denied
.claude/agents/reviewer.md the read-only reviewer sub-agent (disallowedTools in its front matter)
specs/                     spec-kit style: constitution.md, spec.md, plan.md, tasks.md, converge.md
src/README.md              the package map (the only file allowed under src/ before the specs receipt)
src/svcdesk/               the package: config, clock, priority, sla, db, models, service, app, main, healthcheck
tests/                     pytest suite (test_sla.py, test_api.py, test_repo.py), vectors.py, run_tests.py
scripts/run_all_combinations.sh   starts the stack under all eight combinations and runs the tests service
```

## Run it with Docker Compose

The compose file publishes the service on `${SVCDESK_PORT:-8080}`. The examples use port 18080 and the compose
project name `refsvcdesk-build` so they cannot collide with another `svcdesk` stack on the same machine (the
checker uses its own project name); both are optional, `docker compose up --build --wait svcdesk` alone is the
contract.

```bash
SVCDESK_PORT=18080 docker compose -p refsvcdesk-build up --build --wait svcdesk
curl -sS http://127.0.0.1:18080/health
```

Expected (the first build downloads `python:3.13-slim` and the wheels, later builds take about 10 s; `up --wait`
returned in 5.9 s here, far inside the checker's 120 s window):

```
 Image refsvcdesk-build-svcdesk Built
 Container refsvcdesk-build-svcdesk-1 Started
 Container refsvcdesk-build-svcdesk-1 Waiting
 Container refsvcdesk-build-svcdesk-1 Healthy
{"status":"ok","service":"svcdesk","version":"0.1.0","resolutions":{"C1":"wallclock","C2":"immutable","C3":"vip"},"test_clock":true}
```

`/health` carries two extra fields for humans: the active resolution combination and whether the test clock is
on. The checker never reads them; it probes behaviour.

Create a ticket with the test clock at T3 (Friday 17:00 CEST) and ask for its SLA one minute after the
wall-clock acknowledgement target:

```bash
ID=$(curl -sS -X POST http://127.0.0.1:18080/tickets \
  -H 'content-type: application/json' -H 'X-Test-Clock: 2026-10-16T15:00:00Z' \
  -d '{"title":"T3 probe","reporter":{"name":"Anna Kowalska"},"impact":1,"urgency":1}' \
  | tee /dev/stderr | python3 -c 'import json, sys; print(json.load(sys.stdin)["id"])')
curl -sS "http://127.0.0.1:18080/tickets/$ID/sla" -H 'X-Test-Clock: 2026-10-16T15:16:00Z'
echo
```

Expected (ids differ): a P1 with `"created_at":"2026-10-16T15:00:00Z"` and
`"sla":{"ack_due_at":"2026-10-16T15:15:00Z","resolve_due_at":"2026-10-16T19:00:00Z"}` (the C1 = wallclock pair
of LAB1.md check 2.41), then

```
{"priority":"P1","ack_due_at":"2026-10-16T15:15:00Z","resolve_due_at":"2026-10-16T19:00:00Z","ack_breached":true,"resolve_breached":false,"paused":false}
```

Tickets live in the named volume `svcdesk-data` and survive `docker compose restart svcdesk`. Tear down,
removing the volume:

```bash
docker compose -p refsvcdesk-build down -v
```

## Run it natively

```bash
uv venv --python 3.13
uv pip install -e ".[tests]"
SVCDESK_TEST_CLOCK=1 SVCDESK_DB=./data/svcdesk.db uv run uvicorn svcdesk.main:app --port 18080
```

`SVCDESK_DB` defaults to `/data/svcdesk.db`, the path inside the container; natively point it at a writable file
(`data/` is git-ignored). Stop with Ctrl+C. `uv run` uses the `.venv` created by `uv venv` (the project sets
`[tool.uv] managed = false`, so no lock file is written). If a `.venv` already exists, `uv venv` refuses to
replace it: skip that line or add `--clear`.

## Switching the contradiction resolutions

One image, eight behaviours. Three environment variables select the combination at start (LAB1.md section 2 and
7.4); inadmissible values stop the service with a clear message.

| variable | admissible | default | meaning |
|---|---|---|---|
| `SVCDESK_C1` | `wallclock`, `business` | `wallclock` | `wallclock`: P1 targets on the wall clock, P2 to P4 on business hours; `business`: every priority on business hours |
| `SVCDESK_C2` | `reopen`, `immutable` | `immutable` | `reopen`: reopen from closed within 7 days of `closed_at`; `immutable`: closed tickets answer 409 |
| `SVCDESK_C3` | `matrix`, `vip` | `vip` | `vip`: a VIP ticket at P3 or P4 becomes P2; `matrix`: `vip` is stored but ignored |

The same variables reach the `tests` service, so the suite expects the combination the service runs. Export
them once for the whole session, or prefix every compose command with them:

```bash
export SVCDESK_C1=business SVCDESK_PORT=18080
docker compose -p refsvcdesk-build up --build --wait svcdesk
curl -sS http://127.0.0.1:18080/health
echo
curl -sS -X POST http://127.0.0.1:18080/tickets \
  -H 'content-type: application/json' -H 'X-Test-Clock: 2026-10-16T15:00:00Z' \
  -d '{"title":"T3 probe","reporter":{"name":"Anna Kowalska"},"impact":1,"urgency":1}'
echo
docker compose -p refsvcdesk-build down -v
unset SVCDESK_C1
```

Expected: `/health` reports `"C1":"business"` and the T3 ticket carries
`"sla":{"ack_due_at":"2026-10-19T06:15:00Z","resolve_due_at":"2026-10-19T10:00:00Z"}`, the business pair of
check 2.41.

`DECISIONS.md` must declare the combination the service exhibits (the checker's consistency gate, L1-CORE-4).
Never edit it by hand; regenerate it:

```bash
uv run python make_decisions.py business reopen matrix
```

Expected: `wrote .../DECISIONS.md: C1=business C2=reopen C3=matrix`. The script holds a real decision record
for all six resolutions (decision, rejected alternative, reason, service owner, customer outcome, each far above
the 20-character floor of check 3.03); an inadmissible value (`make_decisions.py wallclock sometimes vip`)
prints `error: C2='sometimes' is not admissible; use one of reopen | immutable`, exits 2 and writes nothing.
`--output PATH` writes elsewhere. Restore the shipped defaults with:

```bash
uv run python make_decisions.py wallclock immutable vip
```

`tests/test_repo.py` checks that `DECISIONS.md` is byte for byte the script's output for the combination it
declares, so the file and the prose cannot drift.

## Running the tests

The suite speaks HTTP only. Without `SVCDESK_URL` it starts the reference in-process (a real uvicorn server per
combination, on an ephemeral port, with its own SQLite file) and runs the API tests under **all eight
combinations**; with `SVCDESK_URL` it runs against that service and expects the combination named by
`SVCDESK_C1/C2/C3` (defaults as above).

```bash
uv run pytest -q
```

Expected: `1041 passed in 10.7s` (72 unit tests of the SLA arithmetic, matrix and instants; 36 repository
self-checks; 116 API tests times eight combinations; 5 domain-layer tests of overlapping transitions). Only the
SLA vectors:

```bash
uv run pytest -q tests/test_sla.py
```

Expected: `72 passed in 0.04s`. The same suite with the summary line the checker reads (Stretch S3):

```bash
uv run python tests/run_tests.py
```

Expected last line: `ITSMLAB-TESTS: passed=1041 failed=0`. `SVCDESK_COMBOS=env uv run pytest -q` restricts the
in-process run to the combination named by the environment.

In compose, the `tests` service (profile `tests`, same image, no ports, no bind mounts) runs the suite against
`SVCDESK_URL` (default `http://svcdesk:8080`); it waits for `svcdesk` to be healthy and starts it if needed:

```bash
SVCDESK_PORT=18080 docker compose -p refsvcdesk-build up --build --wait svcdesk
docker compose -p refsvcdesk-build --profile tests run --rm tests
```

Expected tail:

```
220 passed, 3 skipped in 1.69s
ITSMLAB-TESTS: passed=221 failed=0
```

The three skips are tests that need an in-process server (test clock off, persistence across a restart) and the
check that the shipped `DECISIONS.md` declares the defaults, which is skipped whenever `SVCDESK_C*` is set, as
compose always does. The suite also runs from the host against any running service, for example the stack just
started; then tear it down:

```bash
SVCDESK_URL=http://127.0.0.1:18080 uv run python tests/run_tests.py
docker compose -p refsvcdesk-build down -v
```

Expected last line of the tests: `ITSMLAB-TESTS: passed=221 failed=0` (one skip fewer: no `SVCDESK_C*` in
the host environment).

All eight combinations through compose, one line each (rebuilds the image, `down -v` between runs, about
90 s):

```bash
PROJECT=refsvcdesk-build SVCDESK_PORT=18080 scripts/run_all_combinations.sh
```

Expected: eight lines like `wallclock immutable vip     ok    ITSMLAB-TESTS: passed=221 failed=0   health={...}`
and `combinations failed: 0`.

## What the checker sees

| published check (LAB1.md section 3) | where this repository satisfies it |
|---|---|
| L1-CORE-1 compose-up | `docker-compose.yml` (service `svcdesk`, no bind mounts, healthcheck), `Dockerfile` |
| L1-CORE-2 conformance (49 checks) | `src/svcdesk/`; `tests/test_api.py` mirrors every check id under both clocks and all combinations |
| L1-CORE-3 decisions-structure | `DECISIONS.md` (front matter, three sections, five labels); `tests/test_repo.py` |
| L1-CORE-4 decisions-consistency | `make_decisions.py` regenerated for the combination `SVCDESK_C*` selects |
| L1-CORE-5 spec-first | `specs/` receipted before `src/` (a repository-history property; Tier B only) |
| L1-STRETCH-1 converge-report | `specs/converge.md` (traceability table, R-ids in range) |
| L1-STRETCH-2 agent-config | `CLAUDE.md`, `.claude/agents/reviewer.md`, `AGENT-POLICY.md` |
| L1-STRETCH-3 own-tests | the `tests` compose service and its `ITSMLAB-TESTS:` line |
| advisory ai-disclosure | `ai-generated: 100% - ...` in the first ten lines of every file under `src/`, `specs/` and `DECISIONS.md` |

## How it becomes checkpoint/lab-1

Course convention (LAB1.md section 7.4): `checkpoint/lab-N` is the reference solution of Lab N and the starting
point of Lab N+1. After the Lab 1 correction window closes (the second session), in a clone of the course
template repository:

```bash
REF=/absolute/path/to/itsm/2026/grader/reference/svcdesk    # this directory
cd /path/to/template-clone
git switch -c checkpoint-lab-1
rsync -a --exclude .git --exclude .venv --exclude data --exclude report.json --exclude __pycache__ --exclude .pytest_cache "$REF/" ./
python3 make_decisions.py wallclock immutable vip
git add -A && git commit -m "checkpoint/lab-1: reference svcdesk, Lab 1 contradictions resolved as wallclock / immutable / vip"
git tag -a checkpoint/lab-1 -m "Reference solution of Lab 1; starting point of Lab 2"
git push origin checkpoint/lab-1
```

Run `itsmlab verify 1` (checker README) in the clone before pushing the tag; every Core spec must pass and
Stretch must be 3 of 3. The template's own `itsmlab.sh`, `itsmlab.ps1` and `.github/workflows/tier-a.yml` are
kept by `rsync` (it never deletes); `README.md` is overwritten by this file, replace it with a student-facing
one if the template's is preferred. The defaults (`wallclock`, `immutable`, `vip`) are the "one neutral way"
the agenda asks the checkpoint to resolve the contradictions.

A student adopting the checkpoint for Lab 2. Their `origin` is their own repository, created from the template
before term (PREWORK.md step 5); a tag pushed to the template afterwards never appears there, so `git fetch
origin tag checkpoint/lab-1` fails with `couldn't find remote ref`. The tag is fetched from the course template
through a second remote, and `origin` stays theirs for the submissions. The checkpoint replaces every file,
`itsmlab.yaml` included, so the student's own copy (their `repository:`, the value the receipt bot checks
against the roster) is restored from their `main` before only `baselines` is changed:

```bash
git remote add course <URL of the course template repository, from Moodle>     # once
git fetch course --no-tags tag checkpoint/lab-1
git switch -c lab2 checkpoint/lab-1
git checkout main -- itsmlab.yaml                                              # your file, not the checkpoint's
sed -i.bak 's/^baselines: {}/baselines: {lab1: checkpoint}/' itsmlab.yaml && rm itsmlab.yaml.bak
grep -E '^(repository|baselines):' itsmlab.yaml                                # your repository, lab1: checkpoint
git commit -am "Adopt checkpoint/lab-1 as the Lab 2 baseline"
```

(`sed -i.bak` with the suffix attached is the form both GNU sed and the BSD sed of macOS accept; a bare
`sed -i '...'` fails on macOS. PowerShell: `(Get-Content itsmlab.yaml) -replace '^baselines: \{\}',
'baselines: {lab1: checkpoint}' | Set-Content itsmlab.yaml` in place of the sed line, the rest unchanged.)

and declares the adoption in one line of the Lab 2 reasoning artifact. The Lab 2 handout carries these lines.
Without the restore the file names `swasik/itsm-2026-reference`, and the next `submit` is refused by the bot
(`is not the repository registered for <login>`). The self-check `tests/test_repo.py` accepts any
`owner/name` there except the template's placeholder, so the inherited `tests` service keeps passing in the
student's repository.

## Labs 3 and 4 in this tree

**Lab 3** (`design/LAB3.md`): `GET /kb/search` calls the `kb-index` dependency (`src/svcdesk/kb.py`) and a pure ASGI
middleware records every request in `http_server_request_duration_seconds` (`src/svcdesk/metrics.py`, `/metrics`), with
a ladder designed for this repository's kb-index profile (login `itsm-reference` in `itsmlab.yaml`, p99 about 231 ms).
The compose file runs `kb-index` next to `svcdesk`, and a local Prometheus and Grafana under the `observability`
profile, their configuration baked into their images (`prometheus/Dockerfile`, `grafana/Dockerfile`) so the file still
has no bind mount. The artifacts: `slo.md`, `ai-first-draft.md`, `prometheus/alerts.yml` and `alerts_test.yml` (every
mutant killed), `grafana/dashboards/svcdesk-red.json`, and for Stretch `genai/` (a real instrumented call, against
`genai/mock_llm.py` when no model is at hand), `gap.json` with `gap/README.md`, and `k8s/` (manifests only: no cluster
evidence, so that option fails here by design).

```sh
docker compose up -d --build svcdesk kb-index
docker compose --profile observability up -d --build      # Prometheus on 9090, Grafana on 3000
```

**Lab 4** (`design/LAB4.md`): `prometheus/demo-alerts.yml` (the shop's symptom alerts: pages on checkout's errors
and on its latency, warnings on any service's errors and latency), `alertmanager/alertmanager.yml` and
`alertmanager/routing-tests.yml` (routes, and the inhibition pair). The incident is the course's pilot of 27 September
2026, a run of the playground (`student-package/lab4/playground/`) with this directory as `SVCDESK_REPO`:
`incident/tsdb-snapshot.tar.gz` and `incident/ticket.json` (`itsmlab snapshot 4`), `postmortem.md`,
`ai-rca-eval.json` scoring `ai-rca/transcript.md` (qwen3:1.7b), and for Stretch `ai-rca-eval-2.json` scoring
`ai-rca/transcript-2.md` (qwen3:4b-instruct) with `ai-rca/COMPARISON.md`, and `comms-log.md`; `k8s/` has no k8sgpt
output, so that option fails here by design. The snapshot's fault is sealed with the local test key
(`COURSE_SECRET=itsm-local-test-secret`), which the smoke test uses; `ShopCheckoutSlow` was added after the pilot,
as its postmortem's action item says, so the snapshot has no series of it. The pilot ran before the overlay named the
collector's host (LAB4.md 13.13), so the snapshot and the two transcripts were redacted afterwards (LAB4.md 13.18): the
machine's host name became `itsm-playground`, and the series of containers that were not the playground's, with the
17 staleness markers the text format cannot carry, were dropped; every recomputed instant is unchanged.

```sh
itsmlab incident 4          # onset 00:45:35, detection 00:48:09, acknowledgement 00:49:26, recovery 00:56:09
itsmlab verify 4            # Core 5/5, Stretch 2 of 3 (4.06 and 5.06 are the grader's)
```

## Design notes

- `src/svcdesk/sla.py` does all arithmetic on aware UTC datetimes and uses Europe/Warsaw only to locate window
  boundaries; `business_due` consumes the target from consecutive `[08:00, 16:00)` windows with
  `remaining <= available` as the tie rule (T4: a target ending exactly at closing is due at 16:00).
- The test clock is an app-wide FastAPI dependency (`app.bind_clock`): with `SVCDESK_TEST_CLOCK=1` any request
  on a known route with an unparsable or naive `X-Test-Clock` is a 400; without the header `now` is real UTC;
  with the variable off the header is ignored. `now` is decided per request and never compared across requests.
- Each ticket stores which clock its resolution target used (`resolve_clock`), so `paused` follows the clock the
  target was computed with even if the service is later restarted under another `SVCDESK_C1`.
- Error bodies are always `{"error": {"code": ..., "message": ..., ...}}`: `validation_error` (422),
  `invalid_test_clock` (400), `not_found` (404, also for unknown routes), `method_not_allowed` (405),
  `invalid_transition`, `reopen_window_expired`, `ticket_closed` (409).
- `GET /tickets` returns every matching ticket, in insertion order, without pagination.

## Troubleshooting

- **Port already in use**: pick another host port with `SVCDESK_PORT=...`; the container port stays 8080.
- **Tests fail with a wrong SLA pair or a wrong reopen status right after switching a resolution**: the
  `tests` service read different `SVCDESK_C*` values than `svcdesk` did; export the variables once and run
  `up` and `--profile tests run` from the same shell, or `down -v` and start again.
- **`docker compose up --wait` times out**: `docker compose -p refsvcdesk-build logs svcdesk`; the healthcheck
  is `python -m svcdesk.healthcheck` inside the container, so a failure is the app itself (typically an
  inadmissible `SVCDESK_C*` value, printed in the log).
- **`PermissionError: /data` natively**: set `SVCDESK_DB=./data/svcdesk.db` as in the native example.
- **`uv run` cannot find the package**: run from this directory after `uv venv --python 3.13` and
  `uv pip install -e ".[tests]"`.
- **A `400 invalid_test_clock`**: the header must be an RFC 3339 instant with an offset
  (`2026-10-16T15:00:00Z`); `2026-10-16T15:00:00` is naive and rejected.
- **Stale `DECISIONS.md` after switching**: regenerate with `make_decisions.py`, then `docker compose build`
  (the image carries a copy for the in-container self-checks; only its structure is checked there).

## Open questions

Interpretations and disagreements with `design/LAB1.md`, reported here as section 9 asks:

1. **Malformed clock on clock-independent routes.** Section 1.7 says a header that does not parse returns
   400 or 422 and that the header is irrelevant on `GET /tickets` and `GET /tickets/{id}`. The reference takes
   the stricter reading and rejects an unparsable header on every known route (including `/health`); the
   checker only sends malformed clocks in check 2.04 (`POST /tickets`), so both readings pass. Worth stating
   in `API.md` which one students may rely on.
2. **The `tests` service inherits `SVCDESK_C1/C2/C3` through compose interpolation.** The checker's
   eight-combination integration (section 8.3) must export the same variables for `up` and for
   `--profile tests run`, otherwise the suite expects the defaults while the service runs something else.
3. **`/health` exposes the active combination.** Convenient for humans and for the `run_all_combinations.sh`
   record, but the consistency gate must keep probing behaviour (2.35, 2.41, 2.46) rather than trusting it; a
   student could report anything there.
4. **Wrong method on a known path** returns 405 with a JSON `error` body (section 1.6 allows 404 or 405).
5. **Agenda versus design on the number of admissible outcomes.** Agenda section 6 says the conformance
   suite is satisfiable "three different ways"; LAB1.md section 2 defines two resolutions per contradiction,
   eight combinations. The reference follows LAB1.md; the handout should use the same wording.
6. **`SVCDESK_TEST_CLOCK`** accepts `1` and `true` case-insensitively (section 1.7 lists `1` or `true`).
7. **Test counts.** The native run reports 1041 tests (eight combinations in-process, plus five domain-layer
   tests that need the package and are skipped under `SVCDESK_URL`), the compose `tests` service 221; both
   satisfy the `n >= 10` floor of L1-STRETCH-3, but a reader comparing the two numbers should know why they
   differ (see "Running the tests").
