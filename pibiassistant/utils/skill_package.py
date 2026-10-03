# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Claude / Agent Skills packages (.skill zip files): parse and build them safely, in memory.

A package is a folder with SKILL.md (YAML frontmatter + Markdown body) and optional references/, assets/ and
scripts/. Everything here treats the zip as untrusted input: nothing is extracted to disk, nothing is executed,
and paths, sizes, symlinks and secrets are checked before a single byte is stored.
"""

import hashlib
import io
import json
import mimetypes
import re
import stat
import zipfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml

MAX_ZIP_BYTES = 25 * 1024 * 1024
MAX_ENTRIES = 1000
MAX_FILES = 300
MAX_ENTRY_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 50 * 1024 * 1024
MAX_RATIO = 200
MAX_TEXT_INLINE = 1024 * 1024  # larger text files are stored as private Files like binaries
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
RESERVED_WORDS = ("anthropic", "claude")
MAX_DESCRIPTION = 1024
IGNORED_PARTS = {".git", "__pycache__", "__MACOSX"}
IGNORED_NAMES = {".DS_Store", ".gitignore", ".env", "Thumbs.db"}
IGNORED_SUFFIXES = (".pyc", ".pyo")
KIND_BY_FOLDER = {"references": "reference", "assets": "asset", "scripts": "script"}
BINARY_SUFFIXES = {".docx", ".xlsx", ".pptx", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".odt", ".ods", ".woff", ".woff2", ".ttf", ".otf", ".mp3", ".mp4"}
FRONTMATTER_OWN_KEYS = ("name", "description")

SECRET_PATTERNS = (
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}")),
    ("Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OpenAI-style API key", re.compile(r"\bsk-[A-Za-z0-9_\-]{32,}")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY")),
    ("URL with credentials", re.compile(r"https?://[^/\s:@]+:[^/\s@]{3,}@")),
)
REFERENCE_RE = re.compile(r"(?<![\w/.-])((?:references|assets|scripts)/[\w][\w./\-]*[\w])")


class SkillPackageError(Exception):
    """A package the user can fix: the message is safe to show (it never contains a secret value)."""


@dataclass
class SkillFile:
    path: str
    kind: str
    data: bytes = field(repr=False)
    is_text: bool
    size: int
    sha256: str
    mime_type: str

    @property
    def text(self) -> Optional[str]:
        return self.data.decode("utf-8") if self.is_text else None


@dataclass
class SkillPackage:
    name: str
    folder: str
    description: str
    body: str
    frontmatter: Dict[str, Any]
    files: List[SkillFile]
    warnings: List[Dict[str, str]]
    package_sha256: str

    @property
    def version(self) -> str:
        meta = self.frontmatter.get("metadata")
        value = (meta.get("version") if isinstance(meta, dict) else None) or self.frontmatter.get("version")
        return str(value) if value else ""


def _warn(warnings: List[Dict[str, str]], code: str, message: str, path: str = "") -> None:
    warnings.append({"code": code, "message": message, **({"path": path} if path else {})})


def _clean_path(raw: str) -> str:
    if "\\" in raw or raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        raise SkillPackageError(f"Unsafe path in the package: {raw[:80]}")
    parts = raw.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise SkillPackageError(f"Unsafe path in the package: {raw[:80]}")
    return "/".join(parts)


def _ignored(rel: str) -> bool:
    parts = rel.split("/")
    return (
        any(p in IGNORED_PARTS for p in parts[:-1])
        or parts[-1] in IGNORED_NAMES
        or parts[-1].endswith(IGNORED_SUFFIXES)
        or parts[0] in IGNORED_PARTS
    )


def _looks_text(rel: str, data: bytes) -> bool:
    suffix = "." + rel.rsplit(".", 1)[-1].lower() if "." in rel.rsplit("/", 1)[-1] else ""
    if suffix in BINARY_SUFFIXES or b"\x00" in data[:8192]:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def split_frontmatter(text: str) -> (Dict[str, Any], str):
    text = text.lstrip("﻿")
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise SkillPackageError("SKILL.md must start with YAML frontmatter (--- name and description ---).")
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            block = "".join(lines[1:index])
            try:
                meta = yaml.safe_load(block)
            except yaml.YAMLError as e:
                raise SkillPackageError(f"The SKILL.md frontmatter is not valid YAML: {str(e).splitlines()[0][:150]}") from None
            if not isinstance(meta, dict):
                raise SkillPackageError("The SKILL.md frontmatter must be a YAML mapping.")
            return meta, "".join(lines[index + 1 :]).lstrip("\r\n")
    raise SkillPackageError("The SKILL.md frontmatter is not closed with a --- line.")


def _validate_frontmatter(meta: Dict[str, Any], folder: str, warnings: List[Dict[str, str]]) -> (str, str):
    name = meta.get("name")
    if not isinstance(name, str) or not name.strip():
        raise SkillPackageError("The frontmatter needs a name.")
    name = name.strip()
    if len(name) > 64 or not NAME_RE.match(name):
        raise SkillPackageError("name must be 1-64 characters: lowercase letters, digits and single hyphens.")
    if any(word in name for word in RESERVED_WORDS):
        _warn(warnings, "reserved_name", f"The name contains a word Claude reserves ({name}); claude.ai would reject it.")
    description = meta.get("description")
    if not isinstance(description, str) or not description.strip():
        raise SkillPackageError("The frontmatter needs a description (what the skill does and when to use it).")
    description = description.strip()
    if len(description) > MAX_DESCRIPTION:
        raise SkillPackageError(f"description is {len(description)} characters; the limit is {MAX_DESCRIPTION}.")
    if re.search(r"</?[A-Za-z][^>]*>", description):
        _warn(warnings, "description_tags", "The description contains XML-like tags, which Claude does not allow.")
    if folder and folder != name:
        _warn(warnings, "folder_name", f"The folder is called {folder} but the skill name is {name}; the name is used.")
    return name, description


def _scan_secrets(files: List[SkillFile]) -> None:
    hits = []
    for f in files:
        if not f.is_text:
            continue
        text = f.data.decode("utf-8")
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                hits.append(f"{f.path} ({label})")
    if hits:
        raise SkillPackageError(
            "The package seems to contain secrets, so it was not imported: "
            + ", ".join(hits[:8])
            + ". Remove them (and rotate them if they were real) and package it again."
        )


def _read_zip(data: bytes, warnings: List[Dict[str, str]]):
    """(files by path incl. SKILL.md, folder, ignored paths, .git/config text) from a zip, all checks applied."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise SkillPackageError("The file is not a valid .skill (zip) archive.") from None
    infos = archive.infolist()
    if len(infos) > MAX_ENTRIES:
        raise SkillPackageError(f"The package has more than {MAX_ENTRIES} entries.")

    entries: List[tuple] = []
    for info in infos:
        raw = info.filename
        if raw.endswith("/"):
            continue
        rel = _clean_path(raw)
        if info.flag_bits & 0x1:
            raise SkillPackageError("The package is encrypted.")
        if stat.S_ISLNK(info.external_attr >> 16):
            raise SkillPackageError(f"The package contains a symbolic link ({rel[:80]}).")
        entries.append((rel, info))
    if not entries:
        raise SkillPackageError("The package is empty.")

    names = [rel for rel, _ in entries if not rel.startswith("__MACOSX/")]
    if "SKILL.md" in names:
        root = ""
    else:
        tops = {n.split("/", 1)[0] for n in names if "/" in n}
        if len(tops) == 1 and f"{next(iter(tops))}/SKILL.md" in names:
            root = next(iter(tops)) + "/"
        else:
            raise SkillPackageError("SKILL.md was not found at the root of the package (or in its single top folder).")
    folder = root.rstrip("/")

    kept: Dict[str, SkillFile] = {}
    total = 0
    ignored: List[str] = []
    git_config = ""
    for rel_full, info in entries:
        if rel_full.startswith("__MACOSX/"):
            continue
        if root and not rel_full.startswith(root):
            raise SkillPackageError(f"Files outside the skill folder: {rel_full[:80]}")
        rel = rel_full[len(root):]
        if rel == ".git/config" or rel.endswith("/.git/config"):
            git_config = archive.read(info)[:20000].decode("utf-8", "replace")
        if _ignored(rel):
            ignored.append(rel)
            continue
        if info.file_size > MAX_ENTRY_BYTES:
            raise SkillPackageError(f"{rel} is larger than {MAX_ENTRY_BYTES // (1024 * 1024)} MB.")
        if info.compress_size and info.file_size > 1024 * 1024 and info.file_size / info.compress_size > MAX_RATIO:
            raise SkillPackageError(f"{rel} is suspiciously compressed (zip bomb).")
        total += info.file_size
        if total > MAX_TOTAL_BYTES:
            raise SkillPackageError(f"The package is larger than {MAX_TOTAL_BYTES // (1024 * 1024)} MB uncompressed.")
        with archive.open(info) as handle:
            content = handle.read(MAX_ENTRY_BYTES + 1)
        if len(content) > MAX_ENTRY_BYTES:
            raise SkillPackageError(f"{rel} is larger than {MAX_ENTRY_BYTES // (1024 * 1024)} MB.")
        if rel in kept:
            raise SkillPackageError(f"Duplicate entry in the package: {rel[:80]}")
        text = _looks_text(rel, content)
        mime = mimetypes.guess_type(rel)[0] or ("text/plain" if text else "application/octet-stream")
        top = rel.split("/", 1)[0]
        kind = "skill" if rel == "SKILL.md" else KIND_BY_FOLDER.get(top, "other") if "/" in rel else "other"
        kept[rel] = SkillFile(rel, kind, content, text, len(content), hashlib.sha256(content).hexdigest(), mime)
    if len([k for k in kept if k != "SKILL.md"]) > MAX_FILES:
        raise SkillPackageError(f"The package has more than {MAX_FILES} files.")
    if "SKILL.md" not in kept or not kept["SKILL.md"].is_text:
        raise SkillPackageError("SKILL.md was not found or is not text.")
    return kept, folder, ignored, git_config


def _single_markdown(data: bytes) -> SkillFile:
    if len(data) > MAX_TEXT_INLINE:
        raise SkillPackageError("A standalone SKILL.md can be at most 1 MB.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise SkillPackageError("The file is neither a .skill (zip) archive nor a UTF-8 SKILL.md.") from None
    if not text.lstrip("\ufeff").startswith("---"):
        raise SkillPackageError("The file is neither a .skill (zip) archive nor a SKILL.md with YAML frontmatter.")
    return SkillFile("SKILL.md", "skill", data, True, len(data), hashlib.sha256(data).hexdigest(), "text/markdown")


def parse_skill_package(data: bytes) -> SkillPackage:
    """A .skill / .zip archive, or a standalone SKILL.md (a skill that is just instructions)."""
    if not data or len(data) > MAX_ZIP_BYTES:
        raise SkillPackageError(f"The package is empty or larger than {MAX_ZIP_BYTES // (1024 * 1024)} MB.")
    warnings: List[Dict[str, str]] = []
    if data[:2] == b"PK":
        kept, folder, ignored, git_config = _read_zip(data, warnings)
    else:
        kept, folder, ignored, git_config = {"SKILL.md": _single_markdown(data)}, "", [], ""
    if ignored:
        git = [p for p in ignored if p.split("/", 1)[0] == ".git"]
        if git:
            message = f"A .git folder ({len(git)} entries) was found in the package and ignored."
            if re.search(r"://[^/\s:@]+:[^/\s@]+@", git_config):
                message += " Its config contains credentials: rotate that token and package the skill again without .git."
            _warn(warnings, "git_ignored", message)
        other = [p for p in ignored if p.split("/", 1)[0] != ".git"]
        if other:
            _warn(warnings, "junk_ignored", f"Ignored {len(other)} junk file(s): " + ", ".join(other[:6]))

    skill_md = kept.pop("SKILL.md")
    meta, body = split_frontmatter(skill_md.data.decode("utf-8"))
    body = body.strip()
    name, description = _validate_frontmatter(meta, folder, warnings)
    meta = {**meta, "name": name, "description": description}  # the cleaned values are what is stored and exported
    files = sorted(kept.values(), key=lambda f: f.path)
    _scan_secrets([skill_md] + files)

    present = {f.path for f in files}
    missing = []
    for ref in REFERENCE_RE.findall(body):
        ref = ref.rstrip(".,;:)")
        if "." not in ref.rsplit("/", 1)[-1]:
            continue  # a folder named in prose (assets/img for generated output), not a bundled file
        if ref not in present and not any(p.startswith(ref.rstrip("/") + "/") for p in present) and ref not in missing:
            missing.append(ref)
    for ref in missing[:20]:
        _warn(warnings, "missing_file", f"SKILL.md refers to {ref}, which is not in the package.", ref)
    if body.count("\n") + 1 > 500:
        _warn(warnings, "long_body", "SKILL.md is over 500 lines; the spec recommends keeping it shorter and moving detail to references/.")
    scripts = [f.path for f in files if f.kind == "script"]
    if scripts:
        _warn(warnings, "scripts_not_run", f"{len(scripts)} script(s) are stored for the client to read or run; this server never runs them.")

    digest = hashlib.sha256(
        json.dumps({"frontmatter": meta, "body": body, "files": [(f.path, f.sha256) for f in files]}, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return SkillPackage(name, folder, description, body, meta, files, warnings, digest)


def build_skill_package(name: str, frontmatter: Dict[str, Any], body: str, files: List[tuple]) -> bytes:
    """A .skill zip: ``<name>/SKILL.md`` (frontmatter + body) plus ``files`` as (relative path, bytes)."""
    meta = {k: v for k, v in frontmatter.items()}
    front = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, default_flow_style=False, width=100000).rstrip("\n")
    skill_md = f"---\n{front}\n---\n\n{body}".encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as out:
        out.writestr(f"{name}/SKILL.md", skill_md)
        for path, data in files:
            out.writestr(f"{name}/{_clean_path(path)}", data)
    return buffer.getvalue()
