# ai-generated: 100% - Claude Code (Opus 5.5) wrote this file from CI-SPEC.md sections 3.1-3.5; the lecturer reviews it
"""bakeoff.py - scanners' SARIF files and a labels file in, one confusion matrix per tool out (Lab 5).

    python3 bakeoff.py --labels <labels.json> <sarif> [<sarif> ...]

prints

    {"set": ..., "defects": N, "tools": {<tool id>: {"tp", "fp", "fn", "precision", "recall", "f1"}}}

on stdout and exits 0 (CI-SPEC.md P-23). Every function below cites the rule of CI-SPEC.md section 3 it
implements (P-14..P-22). Standard library only, so that it runs as `python3 -S -E bakeoff.py ...`; input files
are opened for reading only.

Where the rules leave a choice, the most literal reading is taken and the comment at that line says so. One
convention runs through the whole file, as P-16 prescribes: a JSON member whose value is `null` counts as absent.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote

# --- P-19: the course's ten classes and the CWE ids that give them -------------------------------------------

CLASS_CWES: dict[str, frozenset[int]] = {
    "secret": frozenset({259, 260, 321, 798}),
    "injection": frozenset({74, 77, 78, 79, 80, 88, 89, 90, 91, 94, 95, 96, 611, 776, 917, 943, 1336}),
    "deserialization": frozenset({502}),
    "weak-crypto": frozenset({261, 326, 327, 328, 330, 331, 338, 759, 760, 916}),
    "insecure-transport": frozenset({295, 297, 319, 322, 757}),
    "path-traversal": frozenset({22, 23, 35, 36, 73}),
    "ssrf": frozenset({918}),
    "vulnerable-dependency": frozenset({937, 1035, 1104, 1395}),
    "misconfiguration": frozenset({16, 215, 250, 489, 668, 732, 1188}),
    "access-control": frozenset({284, 285, 639, 862, 863}),
}
VULNERABLE_DEPENDENCY = "vulnerable-dependency"
OTHER = "other"  # P-19 (d): the class of a result nothing else classifies; it matches no defect

# P-19 (b): tools whose every result has one fixed class.
CLASS_BY_TOOL = {"gitleaks": "secret", "grype": VULNERABLE_DEPENDENCY, "osv-scanner": VULNERABLE_DEPENDENCY}
# P-19 (b): Trivy's rule tags (compared case-insensitively) and the class each gives.
TRIVY_TAG_CLASSES = {
    "vulnerability": VULNERABLE_DEPENDENCY,
    "secret": "secret",
    "misconfiguration": "misconfiguration",
}
# P-19 (c): "CWE-<n>" inside a tag, "CWE" in any letter case and not preceded by a letter or a digit, <n> the whole
# run of digits after the hyphen (leading zeros allowed). "Letter or digit" is read as ASCII A-Z a-z 0-9, the
# alphabet the rest of section 3 spells out (P-15, P-20), and the digits of <n> as ASCII 0-9 (\d would also take
# other scripts' digits). The greedy run makes "CWE-7980" 7980, never 798; "CWE-918a" is 918.
CWE_IN_TAG = re.compile(r"(?<![A-Za-z0-9])cwe-([0-9]+)", re.IGNORECASE | re.ASCII)

# --- P-15: tool ids -------------------------------------------------------------------------------------------

FIXED_TOOL_IDS = {
    "trivy": "trivy",
    "grype": "grype",
    "osv-scanner": "osv-scanner",
    "gitleaks": "gitleaks",
    "semgrep": "semgrep",
    "semgrep oss": "semgrep",
    "semgrep ce": "semgrep",
    "semgrep community edition": "semgrep",
    "semgrep pro": "semgrep",
}
NOT_A_Z_0_9 = re.compile(r"[^a-z0-9]+")
UNKNOWN_TOOL = "unknown"

# --- P-20: package tokens -------------------------------------------------------------------------------------

PACKAGE_TOKEN = re.compile(r"[A-Za-z0-9._-]+")  # a maximal run of A-Z a-z 0-9 . _ -
TOKEN_END_PUNCTUATION = "._-"  # stripped from both ends of a token ("aiohttp." at the end of a sentence)
PEP503_SEPARATORS = re.compile(r"[-_.]+")


def member(value: Any, *path: str) -> Any:
    """`value[path[0]][path[1]]...`, or None as soon as a step is not an object or lacks the key."""
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def is_int(value: Any) -> bool:
    """A JSON integer: Python's bool is an int subclass, and JSON true is not a line number."""
    return isinstance(value, int) and not isinstance(value, bool)


def as_list(value: Any) -> list:
    """A JSON array, or no entries when the member is absent, null or not an array."""
    return value if isinstance(value, list) else []


def tool_id(run: Any) -> str:
    """P-15: the tool id of a run, from `tool.driver.name`."""
    name = member(run, "tool", "driver", "name")
    # A missing, null or non-string name is "a run without a driver name".
    if not isinstance(name, str):
        return UNKNOWN_TOOL
    # Names compare case-insensitively after surrounding whitespace is removed (str.strip(): Unicode whitespace,
    # so a no-break space goes too). Whitespace inside the name is kept: "Semgrep  OSS" is not "Semgrep OSS".
    key = name.strip().lower()
    if key in FIXED_TOOL_IDS:
        return FIXED_TOOL_IDS[key]
    # Otherwise: lower-cased, every run of characters other than a-z and 0-9 replaced by "-", leading and trailing
    # "-" removed; a name that leaves nothing ("", "   ", "!!!") is unknown.
    return NOT_A_Z_0_9.sub("-", key).strip("-") or UNKNOWN_TOOL


def rule_index(run: Any) -> dict[str, Any]:
    """P-19 (c): a run's `tool.driver.rules[]` by `id` - the same run's, never another run's. Rules are found by
    id, never by `ruleIndex` or `result.rule`; with two entries of the same id (the rules do not expect it) the
    first one is the rule."""
    rules: dict[str, Any] = {}
    for rule in as_list(member(run, "tool", "driver", "rules")):
        rule_id = member(rule, "id")
        if isinstance(rule_id, str):
            rules.setdefault(rule_id, rule)
    return rules


def uri_path(uri: str) -> str:
    """P-17: `%XX` escapes decoded, then a `file://` prefix removed (any letter case), then a leading `./` removed,
    in that order and each once."""
    path = unquote(uri)  # UTF-8, as RFC 3986 and SARIF 2.1.0 section 3.4.4 have it
    if path[:7].lower() == "file://":
        path = path[7:]
    if path.startswith("./"):
        path = path[2:]
    return path


def set_file(path: str, root: str) -> str | None:
    """P-17: the result's file when a `/`-separated component equals the set root exactly (case-sensitive), taken
    from the last such component on; None when the result is outside the set. The rest of the path is kept as it
    is (the rules normalise nothing else: a doubled `/` or a `\\` stays)."""
    parts = path.split("/")
    hits = [index for index, part in enumerate(parts) if part == root]
    if not hits:
        return None
    return "/".join(parts[hits[-1]:])


def result_lines(region: Any) -> tuple[int, int] | None:
    """P-18: (start, end) from `region.startLine` (an integer of at least 1) and `region.endLine`; None when the
    result has no lines."""
    start = member(region, "startLine")
    if not is_int(start) or start < 1:
        return None
    end = member(region, "endLine")
    # A missing endLine is startLine; one below startLine is taken as startLine. The rules do not say what a
    # present but non-integer endLine is; it is read as missing.
    if not is_int(end) or end < start:
        end = start
    return start, end


def tags(item: Any) -> list[str]:
    """The string entries of `properties.tags` of a result or a rule (P-19)."""
    return [tag for tag in as_list(member(item, "properties", "tags")) if isinstance(tag, str)]


def result_classes(tool: str, result: Any, rule: Any) -> frozenset[str]:
    """P-19: a result's classes, from the first of (a)..(d) that gives any. `rule` is the result's rule (the
    `tool.driver.rules[]` entry whose id equals its `ruleId`), or None."""
    # (a) `properties.class` of the result (not of its rule), when it is exactly a class name: case-sensitive, no
    # trimming, and "other" is not a class of the table, so it does not count here.
    declared = member(result, "properties", "class")
    if isinstance(declared, str) and declared in CLASS_CWES:
        return frozenset({declared})
    # (b) by tool.
    if tool in CLASS_BY_TOOL:
        return frozenset({CLASS_BY_TOOL[tool]})
    if tool == "trivy":
        # Only the rule's tags are read here (the result's own tags are not); a Trivy result without a rule, or
        # whose rule has none of the three tags, goes on to (c). A rule with several of them gives several classes.
        by_tag = {TRIVY_TAG_CLASSES[tag.lower()] for tag in tags(rule) if tag.lower() in TRIVY_TAG_CLASSES}
        if by_tag:
            return frozenset(by_tag)
    # (c) every class whose CWE list holds a CWE found in the tags of the result or of its rule.
    cwes = {int(match.group(1)) for tag in tags(result) + tags(rule) for match in CWE_IN_TAG.finditer(tag)}
    by_cwe = {name for name, ids in CLASS_CWES.items() if ids & cwes}
    if by_cwe:
        return frozenset(by_cwe)
    # (d)
    return frozenset({OTHER})


def pep503(name: str) -> str:
    """P-20: lower-cased, every run of `-`, `_` and `.` replaced by a single `-` (PEP 503). Applied to the defect's
    package as it is, and to each message token after its end punctuation is stripped (package_tokens)."""
    return PEP503_SEPARATORS.sub("-", name.lower())


def package_tokens(text: Any) -> frozenset[str]:
    """P-20: the PEP 503 forms of the tokens of `message.text` - maximal runs of A-Z a-z 0-9 . _ -, each with any
    `.`, `_` and `-` removed from both ends. A token that is only punctuation ("...", "-") leaves nothing and is
    dropped, so it can never equal a package."""
    if not isinstance(text, str):
        return frozenset()
    stripped = (token.strip(TOKEN_END_PUNCTUATION) for token in PACKAGE_TOKEN.findall(text))
    return frozenset(pep503(token) for token in stripped if token)


@dataclass(frozen=True)
class Finding:
    """One result of a tool that is in the set (P-16, P-17), with what matching and counting need."""

    rule_id: str | None
    file: str
    lines: tuple[int, int] | None  # P-18
    classes: frozenset[str]  # P-19
    packages: frozenset[str]  # P-20: the PEP 503 forms of the tokens of message.text


def finding(tool: str, result: Any, rules: dict[str, Any], root: str) -> Finding | None:
    """P-16 and P-17: the result as a Finding, or None when it is not counted or lies outside the set."""
    if not isinstance(result, dict):
        return None
    # P-16: `kind` absent, null or exactly "fail" (case-sensitive), and `suppressions` absent, null or empty. Any
    # suppression drops the result, whatever its status (SARIF would keep one whose suppressions were all rejected).
    kind = result.get("kind")
    if kind is not None and kind != "fail":
        return None
    if result.get("suppressions"):
        return None
    # P-16: the physicalLocation of the first entry of locations[]; later locations are never read. No locations,
    # no physicalLocation, no uri or an empty uri: the result is ignored. `uriBaseId` is not resolved (P-17 reads
    # the uri alone).
    locations = as_list(result.get("locations"))
    physical = member(locations[0], "physicalLocation") if locations else None
    uri = member(physical, "artifactLocation", "uri")
    if not isinstance(uri, str) or uri == "":
        return None
    file = set_file(uri_path(uri), root)
    if file is None:
        return None  # outside the set: triage material (P-12), not the matrix's business
    rule_id = result.get("ruleId")
    rule_id = rule_id if isinstance(rule_id, str) else None  # `result.rule.id` is not read: the rules say ruleId
    return Finding(
        rule_id=rule_id,
        file=file,
        lines=result_lines(member(physical, "region")),
        classes=result_classes(tool, result, rules.get(rule_id) if rule_id is not None else None),
        # Only message.text is read: a message given as id + arguments, or as markdown, names no package.
        packages=package_tokens(member(result, "message", "text")),
    )


def matches(found: Finding, defect: Any) -> bool:
    """P-20: does this finding match this defect?"""
    if not isinstance(defect, dict) or defect.get("file") != found.file:
        return False
    cls = defect.get("class")
    # "other" matches no defect (P-19 (d)), even a defect labelled "other".
    if not isinstance(cls, str) or cls == OTHER or cls not in found.classes:
        return False
    if cls == VULNERABLE_DEPENDENCY:
        # The message names the package; lines are not compared, even when both sides have them.
        package = defect.get("package")
        return isinstance(package, str) and pep503(package) in found.packages
    # Every other class: the result has lines and they overlap the defect's (both ranges inclusive).
    start, end = defect.get("start_line"), defect.get("end_line")
    if found.lines is None or not is_int(start) or not is_int(end):
        return False
    return found.lines[0] <= end and start <= found.lines[1]


def ratio(numerator: int, denominator: int) -> float | None:
    """P-22: a score rounded to four decimals, null for 0 / 0."""
    return None if denominator == 0 else round(numerator / denominator, 4)


def tool_matrix(findings: list[Finding], defects: list) -> dict[str, Any]:
    """P-21 and P-22 for one tool."""
    found: set[int] = set()  # defects by position, so that a label file with a repeated id still counts each entry
    false_positives: set[tuple] = set()
    for item in findings:
        hits = {index for index, defect in enumerate(defects) if matches(item, defect)}
        found |= hits  # several results on one defect count once; one result may find two defects
        if not hits:
            # FP: the non-matching results, where the same (ruleId, file, start line, end line) counts once. The
            # key is taken over the non-matching results only (filter, then deduplicate); the lines are P-18's,
            # so a missing endLine and an endLine equal to startLine are the same key.
            false_positives.add((item.rule_id, item.file, item.lines))
    tp, fp = len(found), len(false_positives)
    fn = len(defects) - tp
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),  # tp + fn is the number of defects: null when there are none
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
    }


def bake_off(labels: dict[str, Any], documents: list[Any]) -> dict[str, Any]:
    """The whole matrix (P-23) for a parsed labels file (P-14) and parsed SARIF documents."""
    root = labels.get("set")
    defects = as_list(labels.get("defects"))
    per_tool: dict[str, list[Finding]] = {}
    for document in documents:
        for run in as_list(member(document, "runs")):
            if not isinstance(run, dict):
                continue
            tool = tool_id(run)
            # P-15: runs with the same tool id are one tool, across files; P-21/P-23: a tool with a run is listed
            # even when none of its results is in the set.
            bucket = per_tool.setdefault(tool, [])
            rules = rule_index(run)  # a result's rule comes from its own run's driver
            for result in as_list(run.get("results")):
                item = finding(tool, result, rules, root)
                if item is not None:
                    bucket.append(item)
    return {
        "set": root,
        "defects": len(defects),
        "tools": {tool: tool_matrix(per_tool[tool], defects) for tool in sorted(per_tool)},
    }


def load_json(path: str) -> Any:
    # Read-only (P-23); "utf-8-sig" also accepts a file that starts with a byte-order mark.
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bakeoff.py",
        description="Per-tool confusion matrix of SARIF results against a labels file (CI-SPEC.md section 3).",
    )
    parser.add_argument("--labels", required=True, metavar="LABELS.json", help="the labels file (P-14)")
    parser.add_argument("sarif", nargs="+", metavar="SARIF", help="SARIF 2.1.0 files")
    args = parser.parse_args(argv)
    matrix = bake_off(load_json(args.labels), [load_json(path) for path in args.sarif])
    sys.stdout.write(json.dumps(matrix, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
