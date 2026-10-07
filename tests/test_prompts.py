import json

import jinja2
import pytest

from mf.config import settings
from mf.core.hashing import file_sha256
from mf.llm.prompts import all_prompt_files, load_prompt


def test_locked_prompts_unchanged():
    s = settings()
    lock = json.loads((s.prompts_dir / "lockfile.json").read_text(encoding="utf-8"))
    files = all_prompt_files()
    for pid, sha in lock.items():
        assert pid in files, f"locked prompt {pid} was deleted"
        assert file_sha256(files[pid]) == sha, f"locked prompt {pid} changed; create a _v2 file instead"


def test_config_prompts_exist_and_have_front_matter():
    s = settings()
    p = s.pipeline
    ids = p.reasoning_prompts + [p.query_prompt, p.relevance_prompt, p.supervisor_disagreement_prompt,
                                 p.supervisor_update_prompt]
    assert len(set(p.reasoning_prompts)) == p.k_samples
    for pid in ids:
        pr = load_prompt(pid)
        for k in ("id", "version", "purpose", "model_role", "output_format"):
            assert k in pr.meta, (pid, k)


def test_strict_undefined():
    pr = load_prompt("query_gen_v1")
    with pytest.raises(jinja2.UndefinedError):
        pr.render(title="x")  # missing description/today/n_queries
