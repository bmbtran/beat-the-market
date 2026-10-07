"""Prompt files: prompts/<group>/<id>.md with YAML front matter, rendered by Jinja2 (StrictUndefined).

The sha256 of the prompt FILE is part of every LLM cache key, so editing a prompt invalidates only
the calls that used it. Released prompts are frozen via prompts/lockfile.json (tests/test_prompts.py).

Template convention: the body may contain a line `=== USER ===`; text above it is the system prompt,
text below is the user message. Without the marker, the whole body is the user message.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import jinja2
import yaml

from mf.config import settings
from mf.core.hashing import file_sha256

USER_MARKER = "=== USER ==="
_env = jinja2.Environment(undefined=jinja2.StrictUndefined, keep_trailing_newline=False,
                          trim_blocks=True, lstrip_blocks=True, autoescape=False)


@dataclass(frozen=True)
class Prompt:
    id: str
    path: Path
    sha: str
    meta: dict
    system_template: str | None
    user_template: str

    def render(self, **ctx) -> tuple[str | None, str]:
        system = _env.from_string(self.system_template).render(**ctx).strip() if self.system_template else None
        user = _env.from_string(self.user_template).render(**ctx).strip()
        return system, user


def find_prompt_file(prompt_id: str, root: Path | None = None) -> Path:
    root = root or settings().prompts_dir
    hits = list(root.rglob(f"{prompt_id}.md"))
    if len(hits) != 1:
        raise FileNotFoundError(f"prompt {prompt_id!r}: found {len(hits)} files under {root}")
    return hits[0]


def parse_prompt_file(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing YAML front matter")
    _, fm, body = text.split("---\n", 2)
    return yaml.safe_load(fm) or {}, body


@lru_cache(maxsize=None)
def load_prompt(prompt_id: str) -> Prompt:
    path = find_prompt_file(prompt_id)
    meta, body = parse_prompt_file(path)
    if meta.get("id") != prompt_id:
        raise ValueError(f"{path}: front-matter id {meta.get('id')!r} != {prompt_id!r}")
    if USER_MARKER in body:
        sys_t, user_t = body.split(USER_MARKER, 1)
    else:
        sys_t, user_t = None, body
    return Prompt(prompt_id, path, file_sha256(path), meta, sys_t, user_t)


def all_prompt_files(root: Path | None = None) -> dict[str, Path]:
    root = root or settings().prompts_dir
    return {p.stem: p for p in sorted(root.rglob("*.md")) if p.name != "CHANGELOG.md"}
