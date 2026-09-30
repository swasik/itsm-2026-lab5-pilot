---
lab5_triage:
  image: ghcr.io/swasik/itsm-2026-lab5-pilot@sha256:88d0eefca5c0c0ec8fcbaca7c3cf4a87a3cd643caa54376f8f653217e03c9270
  sarif_receipt: 9001
---
<!-- ai-generated: 100% - Claude Code (Opus 5.5) wrote this triage for the course reference from the hosted pilot of 30 September 2026 (design/LAB5.md 11 item 8); the lecturer reviews it -->
# Triage

The reference, as run in the Lab 5 hosted pilot (`swasik/itsm-2026-lab5-pilot`). The image gate failed on the first
run with the reference's Lab 1 Dockerfile; everything below is what it took to turn `main` green, and what the
reporting scanners say about the service's own code in the canary run's SARIF (CI-SPEC.md P-12).

| Tool | Rule | Decision | Reason |
|---|---|---|---|
| trivy | CVE-2026-13221 | fix | perl-base 5.40.1-6 in the image (CRITICAL, fixed in 5.40.1-6+deb13u1); `apt-get upgrade` in the Dockerfile installs the fix, and with it the other fixable Debian packages the gate listed (openssl, libpcre2, libsqlite3, gzip) |
| trivy | GHSA-6v7p-g79w-8964 | ignore | msgpack 1.1.2 inside pip itself (pip/_vendor): no pip release ships the fixed 1.2.1 yet, and pip only installs the image at build time - the service never calls it. Ignored until 2026-12-28, reason above the entry in .trivyignore |
| trivy | CVE-2025-47273 | ignore | setuptools 70.3.0's pkg_resources, also vendored inside pip: the flaw is in PackageIndex downloads, which nothing in the image runs; no pip release has the fixed 78.1.1. Ignored until 2026-12-28 |
| semgrep | python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query | false-positive | src/svcdesk/db.py lines 122-125, 131 and 148: the SQL text is assembled from the module's constant COLUMNS and from fixed clause strings; every value is a bound `?` parameter. The rule reports any execute() whose text is not a literal |
| semgrep | python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected | false-positive | src/svcdesk/healthcheck.py line 14 opens http://127.0.0.1:<port>/health, the port from the container's own SVCDESK_PORT_INTERNAL; nothing a client sends reaches the URL, so there is no SSRF |
| semgrep | package_managers.uv.uv-missing-dependency-cooldown.uv-missing-dependency-cooldown | accept | pyproject.toml has no dependency cooldown: a package registered days ago could be installed the day it appears (Lecture 5, slide 27). Accepted because the reference pins every version by hand and has no lock file; revisit when it moves to uv's lock file, before 2027-01-16 |

## Bake-off

Eight labelled defects in this canary set (three code defects, three credentials, two pins; three of its six modules
are decoys). Trivy found 4 of 8 (both pins and the two credentials its secret rules know) with one false positive, the
jwt.io sample token: precision 0.80, recall 0.50, F1 0.62. gitleaks found the three credentials it can see and, like
Trivy and Semgrep, called the sample token a secret: 3 of 8, precision 0.75. Grype and OSV-Scanner found exactly the
two pins and nothing else: precision 1.0, recall 0.25 - their whole job, done perfectly. Semgrep was the worst of the
five here: 2 true positives (the pickled cookie and the CMDB token) against 4 false ones - the allow-listed ORDER BY, the
int()-cast %d query (reported by two rules, so counted twice) and the sample token - so precision 0.33 at recall 0.25. The path traversal and the predictable reset tokens were seen by no scanner at all.

For a gate I would keep Trivy on dependencies and gitleaks on secrets, as the course's pipeline does: both have high
precision, so a red build means something, and a gate that is wrong four times in six (Semgrep on this set) teaches
people to ignore it - Lecture 4's alert fatigue again. Semgrep belongs in review, not in the gate. The AI reviewer's
line (8 of 8, precision 0.80) is not evidence of anything: the model that reviewed the set also wrote the pool, so the
review was not blind - it is in the pilot to test the mechanics of the local route only. And every recall here is an
upper bound: these defects were seeded, and seeded defects flatter every detector.
