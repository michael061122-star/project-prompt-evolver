#!/usr/bin/env python3
"""Offline prompt-library checks and publication plans; Python standard library only.

No command contacts GitHub, reads credentials, or publishes files. Plans must be
executed through the user's existing, authorized GitHub tools.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path, PurePosixPath
from urllib.parse import quote


class Blocked(ValueError):
    """A recoverable workflow constraint; the draft remains on disk."""


SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
COMMIT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
SEMVER = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
VARIABLE = re.compile(r"\{\{\s*([a-z][a-z0-9_]*)\s*\}\}")
LEVELS = {"reviewed", "single-project", "replayed"}
CORE_FIELDS = {
    "schema_version", "id", "title", "version", "summary", "tags", "inputs",
    "requires", "validation", "lineage",
}
SECRET_RULES = {
    "github-token": r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b",
    "api-key": r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}\b",
    "aws-access-key": r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
    "private-key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "credential-url": r"https?://[^\s/:@]+:[^\s/@]+@",
    "bearer-token": r"(?i)\bbearer\s+[A-Za-z0-9_.~-]{20,}",
    "personal-path": r"(?i)(?:[A-Z]:[\\/]Users[\\/][^\s/\\]+|/(?:Users|home)/[^\s/]+)",
    "raw-chat-marker": r"<\|(?:im_start|im_end|start_header_id)\|>",
}


def require(condition, message):
    if not condition:
        raise Blocked(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def normalize(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def digest(text):
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def read_text(path):
    result = normalize(Path(path).read_text(encoding="utf-8-sig"))
    require("\x00" not in result, "Only UTF-8 text files are supported.")
    return result


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON object key.")
        result[key] = value
    return result


def decode(text):
    try:
        return json.loads(text, object_pairs_hook=unique_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(Blocked("Non-finite JSON number.")))
    except json.JSONDecodeError as exc:
        raise Blocked(f"Invalid JSON at line {exc.lineno}; check syntax locally.") from None


def load_json(path):
    return decode(read_text(path))


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_bytes(normalize(text).encode("utf-8"))
    temporary.replace(path)


def write_json(path, value):
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def relative_path(value):
    require(isinstance(value, str) and value and "\\" not in value and ":" not in value,
            "Repository paths must be relative POSIX paths.")
    parts = value.split("/")
    require(all(p and p not in {".", "..", ".git", ".prompt-evolver"} for p in parts),
            "Unsafe or private repository path.")
    require(not PurePosixPath(value).is_absolute(), "Absolute repository path is forbidden.")
    return value


def within(root, relative):
    relative_path(relative)
    root = Path(os.path.abspath(root)).resolve()
    path = root.joinpath(*relative.split("/")).resolve()
    require(path.is_relative_to(root), "Path escapes the supplied snapshot directory.")
    return path


def version(value):
    require(matches(SEMVER, value), "Version must be MAJOR.MINOR.PATCH without a v prefix.")
    return tuple(map(int, value.split(".")))


def source_identity(value):
    require(isinstance(value, dict), "Source identity must be an object.")
    require(set(value) == {"repository", "path", "commit", "id", "version", "sha256"},
            "Source identity has missing or unsupported fields.")
    require(matches(REPOSITORY, value["repository"]), "Invalid source repository.")
    relative_path(value["path"])
    require(matches(COMMIT, value["commit"]), "A full immutable source commit SHA is required.")
    require(matches(SLUG, value["id"]) and len(value["id"]) <= 64, "Invalid source ID.")
    require(matches(SHA256, value["sha256"]), "Invalid source content hash.")
    version(value["version"])


def parse_prompt(text):
    text = normalize(text)
    match = re.fullmatch(r"---\n(.*?)\n---\n?(.*)", text, re.S)
    require(match is not None, "Prompt must contain --- delimited JSON metadata, then Markdown.")
    metadata, body = decode(match[1]), match[2]
    require(isinstance(metadata, dict), "Prompt metadata must be an object.")
    require(CORE_FIELDS <= set(metadata) <= CORE_FIELDS | {"integration_base"},
            "Prompt metadata has missing or unsupported fields.")
    require(type(metadata["schema_version"]) is int and metadata["schema_version"] == 1,
            "Unsupported prompt schema.")
    require(matches(SLUG, metadata["id"]) and len(metadata["id"]) <= 64, "Invalid prompt ID.")
    version(metadata["version"])
    for field in ("title", "summary"):
        require(nonempty(metadata[field]), f"Missing prompt {field}.")
    for field in ("tags", "requires"):
        require(isinstance(metadata[field], list) and all(nonempty(v) for v in metadata[field]),
                f"{field} must be a list of non-empty strings.")
    require(isinstance(metadata["inputs"], list), "inputs must be a list.")
    names = set()
    for item in metadata["inputs"]:
        require(isinstance(item, dict) and {"name", "required", "description"} <= set(item)
                <= {"name", "required", "description", "default"}, "Invalid input definition.")
        name = item["name"]
        require(isinstance(name, str) and re.fullmatch(r"[a-z][a-z0-9_]*", name), "Invalid input name.")
        require(name not in names, "Duplicate input name.")
        names.add(name)
        require(type(item["required"]) is bool and nonempty(item["description"]),
                "Inputs require a boolean required flag and a description.")
    require(nonempty(body), "Prompt body cannot be empty.")
    require(set(VARIABLE.findall(body)) <= names, "Body contains an undeclared input variable.")
    validation = metadata["validation"]
    require(isinstance(validation, dict) and set(validation) == {"level", "note"}
            and validation["level"] in LEVELS and nonempty(validation["note"]),
            "Validation requires a supported level and truthful scope note.")
    lineage = metadata["lineage"]
    if lineage is not None:
        require(isinstance(lineage, dict) and set(lineage) == {"kind", "source"}
                and lineage["kind"] in {"update", "variant"}, "Invalid lineage.")
        source_identity(lineage["source"])
        require((lineage["source"]["id"] == metadata["id"]) == (lineage["kind"] == "update"),
                "Updates retain an ID; variants must use a different ID.")
    if metadata.get("integration_base") is not None:
        source_identity(metadata["integration_base"])
        require(metadata["integration_base"]["id"] == metadata["id"], "Integration base ID mismatch.")
    return metadata, body


def substantive(text):
    metadata, body = parse_prompt(text)
    metadata = {k: v for k, v in metadata.items() if k not in {"version", "lineage", "integration_base"}}
    body = "\n".join(line.rstrip() for line in body.strip().splitlines())
    return canonical(metadata) + "\n" + body


def findings(text, deny_terms=()):
    result = []
    for rule, expression in SECRET_RULES.items():
        for match in re.finditer(expression, text):
            result.append({"rule": rule, "line": text.count("\n", 0, match.start()) + 1})
    folded = text.casefold()
    for term in deny_terms:
        if term.casefold() in folded:
            result.append({"rule": "configured-private-term"})
    return result


def validate_config(value):
    require(isinstance(value, dict) and type(value.get("schema_version")) is int
            and value.get("schema_version") == 1, "Unsupported config schema.")
    library, publishing = value.get("library", {}), value.get("publishing", {})
    require(matches(REPOSITORY, library.get("repository")), "Configure a real owner/repository first.")
    require("YOUR-" not in library["repository"], "Replace the example repository before use.")
    relative_path(library.get("prefix"))
    branch = library.get("branch")
    require(nonempty(branch) and not branch.startswith(("-", "/")) and not branch.endswith(("/", "."))
            and branch != "@" and all(not part.startswith(".") and not part.endswith(".lock") for part in branch.split("/"))
            and not re.search(r"[\s~^:?*\[\\\x00-\x1f\x7f]|\.\.|@\{|//", branch), "Invalid target branch.")
    require(publishing.get("mode") in {"direct", "pr"} and type(publishing.get("authorized")) is bool,
            "Configure publishing mode and authorization status.")
    terms = value.get("privacy", {}).get("deny_terms", [])
    require(isinstance(terms, list) and all(nonempty(term) for term in terms), "Invalid private-term list.")
    return value


def config(path):
    return validate_config(load_json(path))


def identity(repository, path, commit, text):
    metadata, _ = parse_prompt(text)
    result = {"repository": repository, "path": path, "commit": commit,
              "id": metadata["id"], "version": metadata["version"], "sha256": digest(text)}
    source_identity(result)
    return result


def record_use(prompt, repository, path, commit, out):
    text = read_text(prompt)
    source = identity(repository, path, commit, text)
    out = Path(out)
    require(not out.exists(), "Run directory already exists; reuse its record or choose a new directory.")
    out.mkdir(parents=True)
    write_text(out / "base.md", text)
    record = {"schema_version": 1, "source": source, "snapshot": "base.md"}
    write_json(out / "run.json", record)
    return {"status": "recorded", "run": str(out / "run.json"), "source": source}


def snapshot(root, repository, branch, commit, present, absent):
    require(matches(REPOSITORY, repository) and matches(COMMIT, commit), "Invalid snapshot source.")
    require(nonempty(branch), "Snapshot branch is required.")
    require(set(present).isdisjoint(absent) and len(set(present + absent)) == len(present + absent),
            "Snapshot paths must be unique and cannot be both present and absent.")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    files = {}
    for path in present:
        files[path] = digest(read_text(within(root, path)))
    for path in absent:
        require(not within(root, path).exists(), "An absent remote path has a local file; inspect the snapshot.")
        files[path] = None
    value = {"schema_version": 1, "repository": repository, "branch": branch, "commit": commit, "files": files}
    write_json(root / ".snapshot.json", value)
    return {"status": "snapshot-recorded", "paths": len(files), "commit": commit}


def snapshot_record(root, repository, branch, commit):
    value = load_json(Path(root) / ".snapshot.json")
    require(isinstance(value, dict) and value.get("schema_version") == 1
            and (value.get("repository"), value.get("branch"), value.get("commit")) ==
            (repository, branch, commit) and isinstance(value.get("files"), dict),
            "Snapshot does not identify the requested immutable remote commit.")
    return value


def snapshot_file(root, record, path):
    require(path in record["files"], "Remote path was not inspected; record existence or verified absence first.")
    local = within(root, path)
    expected = record["files"][path]
    if expected is None:
        require(not local.exists(), "An absent snapshot path has unexpected local content.")
        return None
    require(matches(SHA256, expected), "Invalid snapshot content hash.")
    text = read_text(local)
    require(digest(text) == expected, "Downloaded remote snapshot content has changed.")
    return text


def read_run(path):
    run = load_json(path)
    require(isinstance(run, dict) and run.get("schema_version") == 1
            and run.get("snapshot") == "base.md", "Invalid local run record.")
    source_identity(run["source"])
    base = read_text(within(Path(path).parent, run["snapshot"]))
    expected = identity(run["source"]["repository"], run["source"]["path"], run["source"]["commit"], base)
    require(expected == run["source"], "Original prompt snapshot or source record has changed.")
    return run["source"]


def review_template(prompt, note, out):
    value = {
        "schema_version": 1,
        "candidate_sha256": digest(read_text(prompt)),
        "change_note_sha256": digest(read_text(note)),
        "completion": {"status": "incomplete", "evidence": []},
        "privacy_reviewed": False,
        "generalization_reviewed": False,
        "baseline_reviewed": False,
        "validation_level": "reviewed",
        "validation_evidence": [],
    }
    write_json(out, value)
    return {"status": "review-required", "review": str(out)}


def review_check(path, prompt, note, metadata):
    value = load_json(path)
    require(isinstance(value, dict) and value.get("schema_version") == 1, "Invalid review record.")
    require(value.get("candidate_sha256") == digest(prompt)
            and value.get("change_note_sha256") == digest(note), "Review is stale; review the changed files.")
    completion = value.get("completion", {})
    require(completion.get("status") in {"user-accepted", "checks-passed", "user-and-checks"},
            "No supported project completion evidence.")
    require(isinstance(completion.get("evidence"), list) and completion["evidence"]
            and all(nonempty(v) for v in completion["evidence"]), "Record actual completion evidence locally.")
    require(value.get("privacy_reviewed") is True and value.get("generalization_reviewed") is True,
            "Semantic privacy and generalization review are required.")
    if metadata["lineage"] is not None:
        require(value.get("baseline_reviewed") is True, "Review the actual baseline before an iteration.")
    require(value.get("validation_level") == metadata["validation"]["level"], "Validation scope mismatch.")
    require(isinstance(value.get("validation_evidence"), list) and value["validation_evidence"]
            and all(nonempty(v) for v in value["validation_evidence"]), "Record the validation actually performed.")


def operation_id(payload):
    return digest(canonical({k: v for k, v in payload.items() if k != "operation_id"}))


def make_plan(prompt_path, note_path, library_root, head, config_path, review_path, run_path=None):
    cfg = config(config_path)
    require(cfg["publishing"]["authorized"], "Public publishing has not been authorized in the configured scope.")
    require(matches(COMMIT, head), "Read and supply the full current remote branch head SHA.")
    prompt, note = read_text(prompt_path), read_text(note_path)
    metadata, _ = parse_prompt(prompt)
    require(nonempty(note), "A sanitized change note is required.")
    terms = cfg.get("privacy", {}).get("deny_terms", [])
    for name, content in (("prompt", prompt), ("change-note", note)):
        issues = findings(content, terms)
        require(not issues, f"Publication blocked by {name} privacy scan; run check for rule names.")
    lib = cfg["library"]
    prompt_path_in_repo = f"{lib['prefix']}/{metadata['id']}/prompt.md"
    record = snapshot_record(library_root, lib["repository"], lib["branch"], head)
    current = snapshot_file(library_root, record, prompt_path_in_repo)
    current_metadata = parse_prompt(current)[0] if current is not None else None
    if current is not None and substantive(current) == substantive(prompt):
        return {"status": "no-op", "reason": "No reusable content change; no version or remote write needed.",
                "id": current_metadata["id"], "version": current_metadata["version"]}
    source = read_run(run_path) if run_path else None
    lineage = metadata["lineage"]
    if current is not None:
        require(current_metadata["id"] == metadata["id"], "Remote file ID does not match its target path.")
        require(source is not None and lineage is not None and lineage["kind"] == "update",
                "Updating an existing prompt requires its actual usage record and update lineage.")
        require(version(metadata["version"]) > version(current_metadata["version"]),
                "An update version must be greater than the current remote version.")
    if lineage is None:
        require(source is None and current is None, "New prompts cannot discard an existing source.")
        require(metadata.get("integration_base") is None, "A new prompt cannot have an integration base.")
    else:
        require(source == lineage["source"], "Candidate lineage must match the recorded, actually used version.")
        require(source["repository"] == lib["repository"], "Cross-library import requires a separate reviewed import.")
        require(source["path"] == f"{lib['prefix']}/{source['id']}/prompt.md", "Source path is outside this library layout.")
        if lineage["kind"] == "update":
            require(current is not None, "The update target is missing; inspect remote history instead of recreating it.")
            if digest(current) != source["sha256"]:
                expected = identity(lib["repository"], prompt_path_in_repo, head, current)
                require(metadata.get("integration_base") == expected,
                        "Remote prompt has advanced; perform a three-way integration and record integration_base.")
            elif metadata.get("integration_base") is not None:
                require(metadata["integration_base"] == identity(lib["repository"], prompt_path_in_repo, head, current),
                        "Integration base is stale.")
        else:
            require(current is None and metadata.get("integration_base") is None,
                    "A variant must create a new ID without an integration base.")
    review_check(review_path, prompt, note, metadata)
    note_path_in_repo = f"{lib['prefix']}/{metadata['id']}/changes/{metadata['version']}.md"
    require(snapshot_file(library_root, record, note_path_in_repo) is None,
            "This version already has a change record; inspect it first.")
    payload = {
        "schema_version": 1, "repository": lib["repository"], "base_branch": lib["branch"],
        "mode": cfg["publishing"]["mode"], "expected_head": head,
        "prompt_id": metadata["id"], "version": metadata["version"],
        "kind": lineage["kind"] if lineage else "new",
        "files": [
            {"path": prompt_path_in_repo, "content": prompt, "sha256": digest(prompt),
             "previous_sha256": digest(current) if current is not None else None},
            {"path": note_path_in_repo, "content": note, "sha256": digest(note), "previous_sha256": None},
        ],
    }
    payload["operation_id"] = operation_id(payload)
    return {"status": "ready", "plan": payload}


def verify_plan(plan, config_path):
    cfg = config(config_path)
    require(isinstance(plan, dict) and plan.get("schema_version") == 1, "Invalid plan schema.")
    require(plan.get("operation_id") == operation_id(plan), "Plan fingerprint mismatch; regenerate the plan.")
    require(cfg["publishing"]["authorized"], "Public publishing is not authorized in this scope.")
    lib = cfg["library"]
    require((plan.get("repository"), plan.get("base_branch"), plan.get("mode")) ==
            (lib["repository"], lib["branch"], cfg["publishing"]["mode"]), "Plan does not match current configuration.")
    require(matches(COMMIT, plan.get("expected_head")), "Invalid expected remote head.")
    require(matches(SLUG, plan.get("prompt_id")), "Invalid plan prompt ID.")
    version(plan.get("version"))
    expected_paths = {f"{lib['prefix']}/{plan['prompt_id']}/prompt.md",
                      f"{lib['prefix']}/{plan['prompt_id']}/changes/{plan['version']}.md"}
    files = plan.get("files", [])
    require(isinstance(files, list) and len(files) == 2 and {v["path"] for v in files} == expected_paths,
            "Plan may only contain the prompt and its version change note.")
    for item in files:
        relative_path(item["path"])
        require(item["sha256"] == digest(item["content"]), "Plan file content hash mismatch.")
        require(item["previous_sha256"] is None or matches(SHA256, item["previous_sha256"]),
                "Invalid file precondition.")
        require(not findings(item["content"], cfg.get("privacy", {}).get("deny_terms", [])),
                "Plan privacy scan failed.")
        if item["path"].endswith("/prompt.md"):
            metadata, _ = parse_prompt(item["content"])
            require((metadata["id"], metadata["version"]) == (plan["prompt_id"], plan["version"]),
                    "Plan prompt identity mismatch.")
    return plan


def publication_branch(plan):
    if plan["mode"] == "direct":
        return plan["base_branch"]
    return f"prompt-evolver/{plan['prompt_id']}-{plan['operation_id'][:12]}"


def receipt(plan_path, config_path, remote_root, commit, branch, out, pr_url=None):
    plan = verify_plan(load_json(plan_path), config_path)
    require(matches(COMMIT, commit), "A verified publication commit is required.")
    require(branch == publication_branch(plan), "Publication branch does not match the plan.")
    if plan["mode"] == "pr":
        require(isinstance(pr_url, str) and re.fullmatch(
            r"https://github\.com/" + re.escape(plan["repository"]) + r"/pull/[1-9]\d*", pr_url),
            "Verify the actual PR URL before recording a PR publication.")
    else:
        require(pr_url is None, "Direct publication does not have a PR URL.")
    record = snapshot_record(remote_root, plan["repository"], branch, commit)
    for item in plan["files"]:
        actual = snapshot_file(remote_root, record, item["path"])
        require(actual is not None and digest(actual) == item["sha256"], "Remote read-back differs from the publication plan.")
    value = {"schema_version": 1, "status": "pr-opened" if pr_url else "committed",
             "operation_id": plan["operation_id"], "repository": plan["repository"],
             "branch": branch, "commit": commit, "prompt_id": plan["prompt_id"],
             "version": plan["version"], "pr_url": pr_url,
             "prompt_url": f"https://github.com/{plan['repository']}/blob/{commit}/{quote(plan['files'][0]['path'], safe='/')}",
             "files": [{"path": f["path"], "sha256": f["sha256"]} for f in plan["files"]]}
    write_json(out, value)
    return value


def search(root, prefix, query):
    root = Path(os.path.abspath(root)).resolve()
    directory = within(root, relative_path(prefix))
    require(directory.is_dir(), "Prompt directory is missing from the local library snapshot.")
    terms = [term.casefold() for term in re.split(r"[\s,，]+", query) if term]
    require(terms, "A search query is required.")
    result, skipped = [], 0
    for path in sorted(directory.glob("*/prompt.md")):
        require(path.resolve().is_relative_to(Path(root).resolve()), "Search path escapes the snapshot.")
        try:
            metadata, _ = parse_prompt(read_text(path))
        except (Blocked, OSError, UnicodeError):
            skipped += 1
            continue
        text = " ".join([metadata["id"], metadata["title"], metadata["summary"], *metadata["tags"]]).casefold()
        score = sum(term in text for term in terms)
        if score:
            result.append({"id": metadata["id"], "title": metadata["title"], "version": metadata["version"],
                           "summary": metadata["summary"], "path": path.relative_to(root).as_posix(), "score": score})
    return {"status": "searched", "matches": sorted(result, key=lambda v: (-v["score"], v["id"])),
            "skipped_invalid_files": skipped}


def cli(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("init-config", help="Write local configuration; never contacts GitHub.")
    p.add_argument("--repo", required=True)
    p.add_argument("--branch", default="main")
    p.add_argument("--prefix", default="prompts")
    p.add_argument("--mode", choices=["direct", "pr"], default="direct")
    p.add_argument("--authorized", action="store_true", help="Record existing human authorization, not a grant of permission.")
    p.add_argument("--deny-term", action="append", default=[])
    p.add_argument("--out", required=True)
    p = commands.add_parser("check", help="Check prompt format and detect common disclosure patterns.")
    p.add_argument("--prompt", required=True)
    p.add_argument("--config")
    p.add_argument("--note")
    p = commands.add_parser("search", help="Find candidates by local prompt metadata.")
    p.add_argument("--library", required=True)
    p.add_argument("--prefix", default="prompts")
    p.add_argument("--query", required=True)
    p = commands.add_parser("record-use", help="Preserve the exact prompt actually used in a project.")
    p.add_argument("--prompt", required=True)
    p.add_argument("--repo", required=True)
    p.add_argument("--path", required=True)
    p.add_argument("--commit", required=True)
    p.add_argument("--out", required=True, help="A new private run directory.")
    p = commands.add_parser("snapshot", help="Record tool-verified remote files and absences at one commit.")
    p.add_argument("--root", required=True)
    p.add_argument("--repo", required=True)
    p.add_argument("--branch", required=True)
    p.add_argument("--commit", required=True)
    p.add_argument("--present", action="append", default=[])
    p.add_argument("--absent", action="append", default=[])
    p = commands.add_parser("review-template", help="Write an unchecked local review record tied to draft hashes.")
    p.add_argument("--prompt", required=True)
    p.add_argument("--note", required=True)
    p.add_argument("--out", required=True)
    p = commands.add_parser("plan", help="Generate a bounded publication plan after actual review.")
    for option in ("prompt", "note", "library", "head", "config", "review", "out"):
        p.add_argument("--" + option, required=True)
    p.add_argument("--run")
    p = commands.add_parser("verify-plan", help="Recheck a saved plan before any remote write.")
    p.add_argument("--plan", required=True)
    p.add_argument("--config", required=True)
    p = commands.add_parser("receipt", help="Verify remote read-back and save a local publication receipt.")
    for option in ("plan", "config", "remote-root", "commit", "branch", "out"):
        p.add_argument("--" + option, required=True)
    p.add_argument("--pr-url")
    args = parser.parse_args(argv)
    if args.command == "init-config":
        require(not Path(args.out).exists(), "Configuration exists; inspect and update it explicitly.")
        value = {"schema_version": 1,
                 "library": {"repository": args.repo, "branch": args.branch, "prefix": args.prefix},
                 "publishing": {"mode": args.mode, "authorized": args.authorized},
                 "privacy": {"deny_terms": args.deny_term}}
        validate_config(value)
        write_json(args.out, value)
        return {"status": "configured", "config": args.out, "publishing_authorized": args.authorized}
    if args.command == "check":
        text = read_text(args.prompt)
        metadata, body = parse_prompt(text)
        terms = config(args.config).get("privacy", {}).get("deny_terms", []) if args.config else []
        issues = [{"file": "prompt", **v} for v in findings(text, terms)]
        if args.note:
            issues.extend({"file": "change-note", **v} for v in findings(read_text(args.note), terms))
        unused = sorted({v["name"] for v in metadata["inputs"]} - set(VARIABLE.findall(body)))
        return {"status": "blocked" if issues else "checked", "id": metadata["id"],
                "version": metadata["version"], "sha256": digest(text), "findings": issues,
                "unused_inputs": unused, "semantic_review_required": True}
    if args.command == "search":
        return search(args.library, args.prefix, args.query)
    if args.command == "record-use":
        return record_use(args.prompt, args.repo, args.path, args.commit, args.out)
    if args.command == "snapshot":
        return snapshot(args.root, args.repo, args.branch, args.commit, args.present, args.absent)
    if args.command == "review-template":
        require(not Path(args.out).exists(), "Review exists; preserve or explicitly update the actual review.")
        return review_template(args.prompt, args.note, args.out)
    if args.command == "plan":
        require(not Path(args.out).exists(), "Plan output exists; use a new attempt file to avoid executing a stale plan.")
        result = make_plan(args.prompt, args.note, args.library, args.head, args.config, args.review, args.run)
        write_json(args.out, result["plan"] if result["status"] == "ready" else result)
        return {k: v for k, v in result.items() if k != "plan"} | {"file": args.out}
    if args.command == "verify-plan":
        plan = verify_plan(load_json(args.plan), args.config)
        return {"status": "ready", "operation_id": plan["operation_id"], "branch": publication_branch(plan),
                "files": [v["path"] for v in plan["files"]]}
    if args.command == "receipt":
        return receipt(args.plan, args.config, args.remote_root, args.commit, args.branch, args.out, args.pr_url)
    raise Blocked("Unsupported command.")


def main():
    try:
        result = cli()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get("status") == "blocked" else 0
    except (Blocked, OSError, UnicodeError) as exc:
        # No offending secret or source excerpt is included in diagnostic messages.
        message = str(exc) if isinstance(exc, Blocked) else "Cannot read or write a local UTF-8 workflow file."
        print(json.dumps({"status": "blocked", "reason": message}, ensure_ascii=False))
        return 2
    except (KeyError, TypeError, AttributeError, IndexError):
        print(json.dumps({"status": "blocked", "reason": "Unsupported document structure; inspect the local schema."}))
        return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
