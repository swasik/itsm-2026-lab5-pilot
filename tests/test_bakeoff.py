# ai-generated: 100% - Claude Code (Opus 5.5) wrote this file from CI-SPEC.md sections 3.1-3.5; the lecturer reviews it
"""Tests of bakeoff.py (Lab 5, CI-SPEC.md P-14..P-24), one group per rule, on small SARIF documents built here.

Every test but the practice-set one is self-contained. The practice set lives in the checker's package, outside
this repository's Docker build context, so that test is skipped where the set is absent (the compose `tests`
service runs this suite inside the image).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BAKEOFF = ROOT / "bakeoff.py"
_PARENTS = Path(__file__).resolve().parents
# merito/itsm/2026/{grader/reference/svcdesk/tests, checker/itsmlab/labs/lab5/data/practice}; in the image the
# file is /app/tests/test_bakeoff.py and has no fifth parent.
PRACTICE = _PARENTS[4] / "checker" / "itsmlab" / "labs" / "lab5" / "data" / "practice" if len(_PARENTS) > 4 else None
TOLERANCE = 0.0005  # P-22 / P-24

ROOT_NAME = "lab5-canary"


def load_bakeoff():
    spec = importlib.util.spec_from_file_location("bakeoff", BAKEOFF)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look their module up while the class is built
    spec.loader.exec_module(module)
    return module


bakeoff = load_bakeoff()


# --- builders ---------------------------------------------------------------------------------------------------


def res(uri, start=None, end=None, rule="r1", text="a finding", **extra):
    """One SARIF result with a single physical location; `start`/`end` go into the region when given."""
    physical = {"artifactLocation": {"uri": uri}}
    region = {}
    if start is not None:
        region["startLine"] = start
    if end is not None:
        region["endLine"] = end
    if region:
        physical["region"] = region
    result = {"ruleId": rule, "message": {"text": text}, "locations": [{"physicalLocation": physical}]}
    result.update(extra)
    return result


def run(name, results=(), rules=()):
    driver = {"rules": list(rules)}
    if name is not None:
        driver["name"] = name
    return {"tool": {"driver": driver}, "results": list(results)}


def rule(rule_id, *tag_values):
    return {"id": rule_id, "properties": {"tags": list(tag_values)}}


def sarif(*runs):
    return {"version": "2.1.0", "runs": list(runs)}


def labels(*defects, root=ROOT_NAME):
    return {"set": root, "defects": list(defects)}


def defect(did, file, cls, start=None, end=None, package=None):
    item = {"id": did, "file": file, "class": cls}
    if package is not None:
        item["package"] = package
    else:
        item["start_line"] = start
        item["end_line"] = start if end is None else end
    return item


def matrix(label_doc, *documents):
    return bakeoff.bake_off(label_doc, list(documents))


def cell(label_doc, *documents, tool):
    return matrix(label_doc, *documents)["tools"][tool]


# One defect of each shape, reused below.
INJ = defect("A1", "lab5-canary/app/a.py", "injection", 10, 12)
SEC = defect("C1", "lab5-canary/config/c.py", "secret", 3)
DEP = defect("D1", "lab5-canary/requirements.txt", "vulnerable-dependency", package="Zope.Interface")
SQLI_RULE = rule("sqli", "CWE-89: Improper Neutralization of Special Elements used in an SQL Command", "security")


def semgrep_hit(uri="lab5-canary/app/a.py", start=11, end=None, **extra):
    return sarif(run("Semgrep OSS", [res(uri, start, end, rule="sqli", **extra)], [SQLI_RULE]))


# --- P-15 tools ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Trivy", "trivy"),
        ("  GRYPE ", "grype"),
        ("OSV-Scanner", "osv-scanner"),
        ("Gitleaks", "gitleaks"),
        ("Semgrep", "semgrep"),
        ("Semgrep OSS", "semgrep"),
        ("SEMGREP PRO", "semgrep"),
        (" semgrep ", "semgrep"),
        ("Semgrep CE", "semgrep"),
        ("semgrep community edition", "semgrep"),
        ("\tSemgrep OSS\n", "semgrep"),  # surrounding whitespace, not only spaces
        ("\u00a0Semgrep Pro\u00a0", "semgrep"),  # str.strip(): Unicode whitespace too
        ("Semgrep  OSS", "semgrep-oss"),  # whitespace inside the name is kept
        ("Semgrep Enterprise", "semgrep-enterprise"),
        ("AI Reviewer!", "ai-reviewer"),
        ("ai-reviewer", "ai-reviewer"),
        ("OpenGrep", "opengrep"),
        ("__My  Tool 2.0__", "my-tool-2-0"),
        ("", "unknown"),
        ("   ", "unknown"),
        (" \t\n", "unknown"),
        ("!!!", "unknown"),  # a name that leaves nothing
        ("\u0141\u00f3d\u017a", "d"),  # non-ASCII letters are not a-z
        (None, "unknown"),
        (42, "unknown"),
    ],
)
def test_p15_tool_id(name, expected):
    assert list(matrix(labels(), sarif(run(name)))["tools"]) == [expected]


def test_p15_run_without_tool_object_is_unknown():
    assert list(matrix(labels(), sarif({"results": []}))["tools"]) == ["unknown"]


def test_p15_runs_with_one_tool_id_are_one_tool_across_files():
    first = sarif(run("Semgrep OSS", [res("lab5-canary/app/a.py", 10, rule="sqli")], [SQLI_RULE]))
    second = sarif(run("semgrep", [res("lab5-canary/config/c.py", 3, rule="key")], [rule("key", "CWE-798")]))
    out = matrix(labels(INJ, SEC), first, second)
    assert list(out["tools"]) == ["semgrep"]
    assert out["tools"]["semgrep"]["tp"] == 2


def test_p15_two_runs_of_one_file_are_separate_tools_when_their_ids_differ():
    doc = sarif(run("Trivy"), run("grype"))
    assert sorted(matrix(labels(), doc)["tools"]) == ["grype", "trivy"]


# --- P-16 results -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["pass", "open", "review", "informational", "notApplicable", "FAIL"])
def test_p16_kinds_other_than_fail_are_not_results(kind):
    assert cell(labels(INJ), semgrep_hit(kind=kind), tool="semgrep")["tp"] == 0


@pytest.mark.parametrize(
    "extra",
    [{}, {"kind": "fail"}, {"kind": None}, {"suppressions": []}, {"suppressions": None}],
    ids=["no-kind", "fail", "null-kind", "empty-suppressions", "null-suppressions"],
)
def test_p16_counted_results(extra):
    assert cell(labels(INJ), semgrep_hit(**extra), tool="semgrep")["tp"] == 1


@pytest.mark.parametrize("status", ["accepted", "underReview", "rejected", None])
def test_p16_any_suppression_drops_the_result_whatever_its_status(status):
    suppression = {"kind": "inSource"}
    if status is not None:
        suppression["status"] = status
    hit = semgrep_hit(suppressions=[suppression])
    assert cell(labels(INJ), hit, tool="semgrep") == {
        "tp": 0, "fp": 0, "fn": 1, "precision": None, "recall": 0.0, "f1": 0.0,
    }


def test_p16_null_members_count_as_absent():
    result = res("lab5-canary/app/a.py", 11, None, rule="sqli", properties={"class": None, "tags": None})
    result["locations"][0]["physicalLocation"]["region"]["endLine"] = None  # missing endLine: startLine
    out = cell(labels(INJ), sarif(run("Semgrep", [result], [SQLI_RULE])), tool="semgrep")
    assert (out["tp"], out["fp"]) == (1, 0)
    for nulled in ({"locations": None}, {"ruleId": None}):
        broken = dict(result, **nulled)
        out = cell(labels(INJ), sarif(run("Semgrep", [broken], [SQLI_RULE])), tool="semgrep")
        assert out["tp"] == 0


def test_p16_only_the_first_location_is_read():
    result = res("app/elsewhere.py", 11, rule="sqli")
    result["locations"].append({"physicalLocation": {"artifactLocation": {"uri": "lab5-canary/app/a.py"},
                                                     "region": {"startLine": 11}}})
    out = cell(labels(INJ), sarif(run("Semgrep", [result], [SQLI_RULE])), tool="semgrep")
    assert (out["tp"], out["fp"]) == (0, 0)


@pytest.mark.parametrize(
    "locations",
    [
        None,
        [],
        [{"logicalLocations": [{"name": "f"}]}],
        [{"physicalLocation": {"region": {"startLine": 11}}}],
        [{"physicalLocation": {"artifactLocation": {"uri": ""}, "region": {"startLine": 11}}}],
    ],
    ids=["no-locations", "empty-locations", "no-physical", "no-uri", "empty-uri"],
)
def test_p16_results_without_a_first_uri_are_ignored(locations):
    result = {"ruleId": "sqli", "message": {"text": "x"}}
    if locations is not None:
        result["locations"] = locations
    out = cell(labels(INJ), sarif(run("Semgrep", [result], [SQLI_RULE])), tool="semgrep")
    assert (out["tp"], out["fp"], out["fn"]) == (0, 0, 1)


# --- P-17 paths and scope -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "uri",
    [
        "lab5-canary/app/a.py",
        "/github/workspace/lab5-canary/app/a.py",
        "file:///src/lab5-canary/app/a.py",
        "FILE:///src/lab5-canary/app/a.py",
        "./lab5-canary/app/a.py",
        "file://./lab5-canary/app/a.py",
        "lab5%2Dcanary/app/%61.py",
        "file%3A///src/lab5-canary/app/a.py",  # decoded first, then the prefix goes
        "lab5-canary/vendor/lab5-canary/app/a.py",  # the last root component counts
    ],
)
def test_p17_paths_that_name_the_file(uri):
    assert cell(labels(INJ), semgrep_hit(uri=uri), tool="semgrep")["tp"] == 1


def test_p17_decoded_escape_becomes_part_of_the_file():
    spaced = defect("A2", "lab5-canary/app/my file.py", "injection", 11)
    assert cell(labels(spaced), semgrep_hit(uri="lab5-canary/app/my%20file.py"), tool="semgrep")["tp"] == 1


@pytest.mark.parametrize(
    "uri",
    [
        "LAB5-CANARY/app/a.py",  # case-sensitive
        "lab5-canary-old/app/a.py",  # a component must equal the root, not start with it
        "src/xlab5-canary/app/a.py",
        "lab5-canary\\app\\a.py",  # only "/" separates components
        "app/a.py",
    ],
)
def test_p17_results_outside_the_set_are_not_counted(uri):
    out = cell(labels(INJ), semgrep_hit(uri=uri), tool="semgrep")
    assert (out["tp"], out["fp"]) == (0, 0)


def test_p17_in_the_set_but_another_file_is_a_false_positive():
    out = cell(labels(INJ), semgrep_hit(uri="lab5-canary/app/b.py"), tool="semgrep")
    assert (out["tp"], out["fp"]) == (0, 1)


def test_p17_the_set_root_comes_from_the_labels():
    other = labels(defect("X1", "hidden-root/app/a.py", "injection", 11), root="hidden-root")
    hit = semgrep_hit(uri="/work/hidden-root/app/a.py")
    assert cell(other, hit, tool="semgrep")["tp"] == 1
    assert cell(labels(INJ), semgrep_hit(uri="hidden-root/app/a.py"), tool="semgrep")["fp"] == 0


def test_p17_a_prefix_is_removed_once_only():
    # "./" is removed once, so "././x" keeps one "./", which is harmless: the file starts at the root component.
    assert cell(labels(INJ), semgrep_hit(uri="././lab5-canary/app/a.py"), tool="semgrep")["tp"] == 1


# --- P-18 lines ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "start, end, hit",
    [
        (12, None, True),  # missing endLine is startLine
        (13, None, False),
        (8, 10, True),  # touches the defect's first line
        (12, 20, True),  # touches its last line
        (8, 9, False),
        (13, 20, False),
        (5, 30, True),  # contains the defect
        (11, 11, True),
        (14, 2, False),  # endLine below startLine is startLine: lines 14..14
        (9, 2, False),  # lines 9..9, not 2..9
    ],
)
def test_p18_lines_and_overlap(start, end, hit):
    out = cell(labels(INJ), semgrep_hit(start=start, end=end), tool="semgrep")
    assert (out["tp"], out["fp"]) == ((1, 0) if hit else (0, 1))


@pytest.mark.parametrize("start", [None, 0, -3, "11", 11.0, True])
def test_p18_no_start_line_means_no_lines(start):
    result = res("lab5-canary/app/a.py", rule="sqli")
    if start is not None:
        result["locations"][0]["physicalLocation"]["region"] = {"startLine": start, "endLine": 12}
    out = cell(labels(INJ), sarif(run("Semgrep", [result], [SQLI_RULE])), tool="semgrep")
    assert (out["tp"], out["fp"]) == (0, 1)  # in the set, so it is still a finding: one that matches nothing


def test_p18_non_integer_end_line_is_read_as_missing():
    assert cell(labels(INJ), semgrep_hit(start=12, end="99"), tool="semgrep")["tp"] == 1
    assert cell(labels(INJ), semgrep_hit(start=9, end="99"), tool="semgrep")["tp"] == 0


# --- P-19 classes -------------------------------------------------------------------------------------------------


def test_p19a_declared_class_wins_over_the_tool():
    leak = res("lab5-canary/app/a.py", 11, rule="generic", properties={"class": "injection"})
    out = cell(labels(INJ, defect("C9", "lab5-canary/app/a.py", "secret", 11)), sarif(run("gitleaks", [leak])),
               tool="gitleaks")
    assert (out["tp"], out["fn"]) == (1, 1)  # the injection defect, not the secret on the same line


def test_p19a_declared_class_wins_over_cwe_tags():
    hit = semgrep_hit(properties={"class": "secret", "tags": ["CWE-89"]})
    out = cell(labels(INJ), hit, tool="semgrep")
    assert (out["tp"], out["fp"]) == (0, 1)


@pytest.mark.parametrize("declared", ["Injection", "sql-injection", " injection", "other", ["injection"], 89])
def test_p19a_only_an_exact_class_name_counts(declared):
    # Falls through to (c): the rule's CWE-89 still makes it an injection.
    hit = semgrep_hit(properties={"class": declared})
    assert cell(labels(INJ), hit, tool="semgrep")["tp"] == 1


def test_p19a_declared_class_of_the_rule_is_not_read():
    leak_rule = {"id": "r", "properties": {"class": "injection", "tags": []}}
    doc = sarif(run("my-tool", [res("lab5-canary/app/a.py", 11, rule="r")], [leak_rule]))
    out = cell(labels(INJ), doc, tool="my-tool")
    assert (out["tp"], out["fp"]) == (0, 1)


def test_p19b_gitleaks_is_secret_whatever_its_tags():
    leak = res("lab5-canary/config/c.py", 3, rule="jwt", properties={"tags": ["CWE-89"]})
    out = cell(labels(SEC, defect("A9", "lab5-canary/config/c.py", "injection", 3)), sarif(run("gitleaks", [leak])),
               tool="gitleaks")
    assert (out["tp"], out["fn"]) == (1, 1)


@pytest.mark.parametrize("tool", ["grype", "osv-scanner"])
def test_p19b_grype_and_osv_are_vulnerable_dependency(tool):
    hit = res("lab5-canary/requirements.txt", 1, rule="GHSA-x", text="package zope.interface 4.0 is vulnerable",
              properties={"tags": ["CWE-798"]})
    out = cell(labels(DEP), sarif(run(tool, [hit])), tool=tool)
    assert (out["tp"], out["fp"]) == (1, 0)


@pytest.mark.parametrize(
    "tag, target",
    [
        ("Vulnerability", DEP),
        ("SECRET", defect("C2", "lab5-canary/requirements.txt", "secret", 1)),
        ("misconfiguration", defect("M1", "lab5-canary/requirements.txt", "misconfiguration", 1)),
    ],
)
def test_p19b_trivy_class_from_its_rule_tags(tag, target):
    doc = sarif(run("Trivy", [res("lab5-canary/requirements.txt", 1, rule="T1",
                                  text="Package: zope_interface\nInstalled Version: 4.0")],
                    [rule("T1", tag, "security", "HIGH")]))
    assert cell(labels(target), doc, tool="trivy")["tp"] == 1


def test_p19b_trivy_rule_without_the_three_tags_goes_on_to_cwe():
    doc = sarif(run("Trivy", [res("lab5-canary/app/a.py", 11, rule="T2")], [rule("T2", "security", "CWE-89")]))
    assert cell(labels(INJ), doc, tool="trivy")["tp"] == 1


def test_p19b_trivy_reads_the_rule_tags_not_the_result_tags():
    result = res("lab5-canary/requirements.txt", 1, rule="T3", text="Package: zope.interface",
                 properties={"tags": ["vulnerability"]})
    doc = sarif(run("Trivy", [result], [rule("T3", "security")]))
    out = cell(labels(DEP), doc, tool="trivy")
    assert (out["tp"], out["fp"]) == (0, 1)


def test_p19b_a_trivy_rule_with_two_of_the_tags_gives_two_classes():
    both = labels(DEP, defect("C3", "lab5-canary/requirements.txt", "secret", 1))
    doc = sarif(run("trivy", [res("lab5-canary/requirements.txt", 1, rule="T4", text="Zope.Interface")],
                    [rule("T4", "vulnerability", "secret")]))
    assert cell(both, doc, tool="trivy")["tp"] == 2


@pytest.mark.parametrize(
    "rule_tags, result_tags",
    [
        (["CWE-89: Improper Neutralization"], []),
        (["cwe-0089"], []),
        (["external/cwe/cwe-089"], []),
        ([], ["CWE-89"]),
        (["security"], ["owasp", "Cwe-89 SQL injection"]),
        (["tag:CWE-89a"], []),  # the digit run ends at the letter
        (["_CWE-89"], []),  # "_" is neither a letter nor a digit
        (["XCWE-78 CWE-89"], []),  # the first is not a CWE, the second is
        (["\u00e9CWE-89"], []),  # "letter" read as A-Z a-z: a non-ASCII letter does not block
    ],
)
def test_p19c_cwe_from_the_tags_of_the_result_or_its_rule(rule_tags, result_tags):
    result = res("lab5-canary/app/a.py", 11, rule="x", properties={"tags": result_tags})
    doc = sarif(run("opengrep", [result], [rule("x", *rule_tags)]))
    assert cell(labels(INJ), doc, tool="opengrep")["tp"] == 1


@pytest.mark.parametrize("tag", ["CWE-890", "CWE-0890", "CWE 89", "CWE89", "CWE-", "89", "XCWE-89", "9CWE-89",
                                 "cwe-\u0668\u0669"])
def test_p19c_tags_that_do_not_hold_cwe_89(tag):
    doc = sarif(run("opengrep", [res("lab5-canary/app/a.py", 11, rule="x")], [rule("x", tag)]))
    out = cell(labels(INJ), doc, tool="opengrep")
    assert (out["tp"], out["fp"]) == (0, 1)


def test_p19c_the_rule_is_found_by_rule_id_not_by_rule_index():
    rules = [rule("other", "CWE-798"), rule("x", "CWE-89")]
    result = res("lab5-canary/app/a.py", 11, rule="x", ruleIndex=0)
    assert cell(labels(INJ), sarif(run("opengrep", [result], rules)), tool="opengrep")["tp"] == 1


def test_p19c_a_rule_of_another_run_is_not_the_results_rule():
    doc = sarif(run("opengrep", [], [rule("x", "CWE-89")]), run("opengrep", [res("lab5-canary/app/a.py", 11, rule="x")]))
    out = cell(labels(INJ), doc, tool="opengrep")
    assert (out["tp"], out["fp"]) == (0, 1)


def test_p19c_several_cwes_give_several_classes_and_one_result_finds_two_defects():
    both = labels(INJ, defect("C4", "lab5-canary/app/a.py", "secret", 12))
    doc = sarif(run("opengrep", [res("lab5-canary/app/a.py", 12, rule="x")], [rule("x", "CWE-798", "CWE-78")]))
    out = cell(both, doc, tool="opengrep")
    assert (out["tp"], out["fp"], out["fn"]) == (2, 0, 0)


def test_p19d_other_matches_no_defect():
    labelled_other = defect("O1", "lab5-canary/app/a.py", "other", 11)
    doc = sarif(run("opengrep", [res("lab5-canary/app/a.py", 11, rule="x")], [rule("x", "CWE-400")]))
    out = cell(labels(INJ, labelled_other), doc, tool="opengrep")
    assert (out["tp"], out["fp"], out["fn"]) == (0, 1, 2)


# --- P-20 matching ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, hit",
    [
        ("A high vulnerability in python package: zope.interface, version 4.0", True),
        ("Package 'zope_interface@4.0' is vulnerable", True),
        ("Package: Zope-Interface\nInstalled Version: 4.0", True),
        ("zope__interface", True),  # a run of separators is one "-"
        ("Outdated pin: zope.interface.", True),  # "." "_" "-" are stripped from both ends of a token
        ("(zope_interface)", True),
        ("--zope-interface--", True),
        ("._zope.interface_.", True),
        ("zope.interfaces 4.0", False),
        ("zopeinterface", False),
        ("zope interface", False),
        ("zope.interface-4.0", False),  # one token, "zope-interface-4-0"
        ("", False),
        ("... - _", False),
    ],
)
def test_p20_the_message_names_the_package(text, hit):
    doc = sarif(run("grype", [res("lab5-canary/requirements.txt", 1, rule="G", text=text)]))
    out = cell(labels(DEP), doc, tool="grype")
    assert (out["tp"], out["fp"]) == ((1, 0) if hit else (0, 1))


def test_p20_dependency_lines_are_not_compared():
    no_region = res("lab5-canary/requirements.txt", rule="O1", text="Package 'zope.interface@4.0' is vulnerable")
    far_line = res("lab5-canary/requirements.txt", 99, rule="O2", text="zope.interface")
    for result in (no_region, far_line):
        assert cell(labels(DEP), sarif(run("osv-scanner", [result])), tool="osv-scanner")["tp"] == 1


def test_p20_dependency_only_in_message_text():
    result = res("lab5-canary/requirements.txt", 1, rule="zope.interface", text="CVE-2099-1")
    result["message"] = {"id": "default", "arguments": ["zope.interface"]}
    out = cell(labels(DEP), sarif(run("grype", [result])), tool="grype")
    assert (out["tp"], out["fp"]) == (0, 1)


def test_p20_dependency_needs_the_same_file():
    doc = sarif(run("grype", [res("lab5-canary/app/requirements.txt", 1, text="zope.interface")]))
    out = cell(labels(DEP), doc, tool="grype")
    assert (out["tp"], out["fp"]) == (0, 1)


def test_p20_class_must_match_even_on_the_defects_lines():
    doc = sarif(run("gitleaks", [res("lab5-canary/app/a.py", 11, rule="generic-api-key")]))
    out = cell(labels(INJ), doc, tool="gitleaks")
    assert (out["tp"], out["fp"]) == (0, 1)


def test_p20_a_line_class_needs_lines():
    doc = sarif(run("gitleaks", [res("lab5-canary/config/c.py", rule="k")]))
    out = cell(labels(SEC), doc, tool="gitleaks")
    assert (out["tp"], out["fp"]) == (0, 1)


def test_p20_one_message_may_name_two_packages():
    second = defect("D2", "lab5-canary/requirements.txt", "vulnerable-dependency", package="aiohttp")
    doc = sarif(run("grype", [res("lab5-canary/requirements.txt", 1, text="aiohttp needs zope.interface")]))
    assert cell(labels(DEP, second), doc, tool="grype")["tp"] == 2


# --- P-21 counting ------------------------------------------------------------------------------------------------


def test_p21_several_results_on_one_defect_count_once():
    doc = sarif(run("Semgrep", [res("lab5-canary/app/a.py", n, rule="sqli") for n in (10, 11, 12)], [SQLI_RULE]))
    assert cell(labels(INJ), doc, tool="semgrep") == {
        "tp": 1, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0,
    }


def test_p21_false_positives_count_once_per_rule_file_and_lines():
    far = "lab5-canary/app/z.py"
    results = [
        res(far, 5, rule="sqli"),
        res(far, 5, 5, rule="sqli", text="another message"),  # same key: a missing endLine is startLine
        res(far, 5, 6, rule="sqli"),  # other end line
        res(far, 5, rule="sqli2"),  # other rule
        res("lab5-canary/app/y.py", 5, rule="sqli"),  # other file
        res(far, rule="sqli"),  # no lines
        res(far, rule="sqli"),  # no lines, again
    ]
    doc = sarif(run("Semgrep", results, [SQLI_RULE, rule("sqli2", "CWE-89")]))
    assert cell(labels(INJ), doc, tool="semgrep")["fp"] == 5


def test_p21_duplicate_osv_results_count_once():
    dup = res("file:///src/lab5-canary/requirements.txt", rule="CVE-1", text="Package 'left-pad@1.0' is vulnerable")
    doc = sarif(run("osv-scanner", [dup, dup, res(dup["locations"][0]["physicalLocation"]["artifactLocation"]["uri"],
                                                  rule="CVE-1", text="Package 'zope.interface@4.0' is vulnerable")]))
    assert cell(labels(DEP), doc, tool="osv-scanner") == {
        "tp": 1, "fp": 1, "fn": 0, "precision": 0.5, "recall": 1.0, "f1": 0.6667,
    }


def test_p21_false_positives_are_deduplicated_across_runs_and_files():
    one = sarif(run("gitleaks", [res("lab5-canary/app/z.py", 4, rule="k")]))
    assert cell(labels(SEC), one, one, tool="gitleaks")["fp"] == 1


def test_p21_fn_counts_every_defect_the_tool_missed_whatever_its_class():
    doc = sarif(run("gitleaks", [res("lab5-canary/config/c.py", 3, rule="k")]))
    out = cell(labels(INJ, SEC, DEP), doc, tool="gitleaks")
    assert (out["tp"], out["fp"], out["fn"]) == (1, 0, 2)


def test_p21_tool_without_results_in_the_set_still_appears():
    doc = sarif(run("Trivy", [res("requirements.txt", 1, rule="CVE-1")]), run("grype"))
    out = matrix(labels(INJ, SEC), doc)
    empty = {"tp": 0, "fp": 0, "fn": 2, "precision": None, "recall": 0.0, "f1": 0.0}
    assert out["tools"] == {"grype": empty, "trivy": empty}


def test_p21_results_outside_the_set_are_never_false_positives():
    doc = sarif(run("Semgrep", [res("src/svcdesk/app.py", 11, rule="sqli")], [SQLI_RULE]))
    assert cell(labels(INJ), doc, tool="semgrep")["fp"] == 0


# --- P-22 scores --------------------------------------------------------------------------------------------------


def test_p22_scores_are_rounded_to_four_decimals():
    three = labels(INJ, SEC, defect("A3", "lab5-canary/app/b.py", "injection", 1))
    doc = sarif(run("Semgrep", [res("lab5-canary/app/a.py", 11, rule="sqli"), res("lab5-canary/app/b.py", 1, rule="sqli"),
                                res("lab5-canary/app/c.py", 1, rule="sqli")], [SQLI_RULE]))
    assert cell(three, doc, tool="semgrep") == {
        "tp": 2, "fp": 1, "fn": 1, "precision": 0.6667, "recall": 0.6667, "f1": 0.6667,
    }


def test_p22_no_defects_and_no_results_is_all_null():
    assert cell(labels(), sarif(run("grype")), tool="grype") == {
        "tp": 0, "fp": 0, "fn": 0, "precision": None, "recall": None, "f1": None,
    }


def test_p22_no_defects_with_false_positives():
    doc = sarif(run("gitleaks", [res("lab5-canary/x", 1, rule="k")]))
    assert cell(labels(), doc, tool="gitleaks") == {
        "tp": 0, "fp": 1, "fn": 0, "precision": 0.0, "recall": None, "f1": 0.0,
    }


def test_p22_helper_rounding():
    assert bakeoff.ratio(2, 9) == 0.2222
    assert bakeoff.ratio(4, 11) == 0.3636
    assert bakeoff.ratio(0, 0) is None


# --- P-23 the command ---------------------------------------------------------------------------------------------


def run_cli(tmp_path, label_doc, *documents):
    label_file = tmp_path / "labels.json"
    label_file.write_text(json.dumps(label_doc), encoding="utf-8")
    paths = []
    for index, document in enumerate(documents):
        path = tmp_path / f"in-{index}.sarif"
        path.write_text(json.dumps(document), encoding="utf-8")
        paths.append(str(path))
    return subprocess.run(
        [sys.executable, "-S", "-E", str(BAKEOFF), "--labels", str(label_file), *paths],
        capture_output=True, text=True, timeout=60, check=False,
    )


def test_p23_command_prints_the_matrix_and_exits_0(tmp_path):
    """Run as the grader runs it: `python3 -S -E` (no site-packages, so a third-party import would fail here)."""
    documents = [semgrep_hit(), sarif(run("gitleaks", [res("lab5-canary/config/c.py", 3, rule="k")]), run("grype"))]
    proc = run_cli(tmp_path, labels(INJ, SEC, DEP), *documents)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out == {
        "set": ROOT_NAME,
        "defects": 3,
        "tools": {
            "gitleaks": {"tp": 1, "fp": 0, "fn": 2, "precision": 1.0, "recall": 0.3333, "f1": 0.5},
            "grype": {"tp": 0, "fp": 0, "fn": 3, "precision": None, "recall": 0.0, "f1": 0.0},
            "semgrep": {"tp": 1, "fp": 0, "fn": 2, "precision": 1.0, "recall": 0.3333, "f1": 0.5},
        },
    }


def test_p23_labels_after_the_sarif_files_and_a_bom(tmp_path):
    label_file = tmp_path / "labels.json"
    label_file.write_bytes(b"\xef\xbb\xbf" + json.dumps(labels(INJ)).encode("utf-8"))
    sarif_file = tmp_path / "s.sarif"
    sarif_file.write_text(json.dumps(semgrep_hit()), encoding="utf-8")
    proc = subprocess.run([sys.executable, "-S", "-E", str(BAKEOFF), str(sarif_file), "--labels", str(label_file)],
                          capture_output=True, text=True, timeout=60, check=False)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["tools"]["semgrep"]["tp"] == 1


def test_p23_empty_runs_list_gives_no_tools(tmp_path):
    proc = run_cli(tmp_path, labels(INJ), sarif())
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == {"set": ROOT_NAME, "defects": 1, "tools": {}}


# --- P-24 the practice set ----------------------------------------------------------------------------------------


def test_p24_practice_set_reproduces_expected_json():
    if PRACTICE is None or not (PRACTICE / "expected.json").is_file():
        pytest.skip("the checker's practice set is not next to this repository (e.g. inside the Docker image)")
    sarifs = sorted(str(p) for p in (PRACTICE / "sarif").glob("*.sarif"))
    proc = subprocess.run(
        [sys.executable, "-S", "-E", str(BAKEOFF), "--labels", str(PRACTICE / "labels.json"), *sarifs],
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    got = json.loads(proc.stdout)
    expected = json.loads((PRACTICE / "expected.json").read_text(encoding="utf-8"))
    assert got["set"] == expected["set"]
    assert got["defects"] == expected["defects"]
    assert sorted(got["tools"]) == sorted(expected["tools"])
    for tool, want in expected["tools"].items():
        have = got["tools"][tool]
        for key in ("tp", "fp", "fn"):
            assert have[key] == want[key], (tool, key)
        for key in ("precision", "recall", "f1"):
            if want[key] is None:
                assert have[key] is None, (tool, key)
            else:
                assert have[key] is not None and abs(have[key] - want[key]) <= TOLERANCE, (tool, key)
