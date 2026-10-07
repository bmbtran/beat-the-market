"""Implementations behind the `mf` CLI commands (cli.py stays a thin typer wrapper)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from mf.config import settings
from mf.data.dataset import read_questions
from mf.schemas import Question


def load_split(split: str, limit: int | None = None) -> list[Question]:
    s = settings()
    ddir = s.data_dir / "dataset"
    if split == "canary":
        qs = read_questions(ddir / "canary_precutoff.jsonl")
    else:
        qs = read_questions(ddir / "questions.jsonl")
        if split in ("dev", "test"):
            qs = [q for q in qs if q.split == split]
        elif split != "all":
            raise ValueError(f"unknown split {split!r} (dev|test|canary|all)")
    qs.sort(key=lambda q: (q.t0, q.qid))
    return qs[:limit] if limit else qs


def retrieve(split: str, limit: int | None, dry_run: bool, allow_spend: bool, max_usd: float | None,
             log=print) -> int:
    from mf.retrieval.pipeline import project_question, retrieve_question, write_results
    from mf.runtime import make_ctx

    if split == "canary":
        log("canary questions are only used for the no-retrieval arm; nothing to retrieve")
        return 0
    qs = load_split(split, limit)
    ctx = make_ctx(prefix=f"bt-retrieve-{split}", max_usd=max_usd, allow_spend=allow_spend and not dry_run)
    s = ctx.s
    if dry_run:
        tot = Counter()
        for q in qs:
            tot.update(project_question(q, ctx.llm, ctx.exa, s))
        net = ctx.llm.network_calls + ctx.exa.network_calls
        log(f"DRY RUN retrieve split={split} n={len(qs)}")
        log(f"  helper LLM calls: {tot['llm_hits']} cached, {tot['llm_misses']} to make")
        log(f"  Exa searches:     {tot['exa_hits']} cached, {tot['exa_misses']} to make")
        log(f"  PROJECTED: anthropic ${tot['anthropic_usd']:.4f}, exa ${tot['exa_usd']:.4f}")
        log(f"  network calls made: {int(net)}")
        return 0
    results, drops = [], Counter()
    for i, q in enumerate(qs):
        r = retrieve_question(q, ctx.llm, ctx.exa, s)
        results.append(r)
        drops.update(r.drop_counts)
        if (i + 1) % 10 == 0 or i + 1 == len(qs):
            log(f"[retrieve] {i + 1}/{len(qs)} kept/q={sum(len(x.kept) for x in results) / len(results):.2f} "
                f"spent this run=${ctx.budget.run_spent():.4f}")
            write_results(s.run_dir, results)
    write_results(s.run_dir, results)
    log(f"evidence written to {s.run_dir.relative_to(s.root).as_posix()}/evidence.jsonl")
    log(f"drop counts: {dict(sorted(drops.items()))}")
    log(f"questions with 0 kept evidence: {sum(1 for r in results if not r.kept)}/{len(results)}")
    log(f"spent this run: ${ctx.budget.run_spent():.4f}")
    return 0


# ---------------------------------------------------------------------------------------------
# forecast / pilot
# ---------------------------------------------------------------------------------------------
ARM_SETS = {"all": ("retrieval", "no_retrieval", "supervisor"), "halawi": ("retrieval",),
            "noret": ("no_retrieval",), "aia": ("retrieval", "supervisor")}


def _split_sets(split: str, arms: tuple[str, ...]) -> tuple[list, set[str], set[str]]:
    """Which questions get which arm. Retrieval arms: dev/test. No-retrieval: test + canary."""
    if split == "all":
        qs = load_split("all") + load_split("canary")
    else:
        qs = load_split(split)
    want_ret = {"dev", "test"} if "retrieval" in arms else set()
    want_noret = {"test", "canary"} if "no_retrieval" in arms else set()
    return qs, want_ret, want_noret


def _pilot_gate(n_uncached: int, ctx, log) -> bool:
    import json

    if n_uncached <= 20:
        return True
    p = ctx.s.state_dir / "pilot.json"
    if not p.exists():
        log(f"REFUSED: {n_uncached} uncached questions (> 20) and no state/pilot.json. Run `mf pilot` first.")
        return False
    pilot = json.loads(p.read_text(encoding="utf-8"))
    per_q = pilot["anthropic_usd_per_question_batch"]
    projected = per_q * n_uncached
    remaining = ctx.s.budget.anthropic_backtest_usd - ctx.budget.spent("anthropic", backtest_only=True)
    log(f"[gate] projected ${projected:.2f} for {n_uncached} uncached questions; remaining backtest ${remaining:.2f}")
    if projected > remaining:
        log("REFUSED: projection exceeds remaining Anthropic backtest budget")
        return False
    return True


def forecast_cmd(split: str, arms: str, limit: int | None, dry_run: bool, allow_spend: bool,
                 max_usd: float | None, use_batch: bool | None = None, log=print) -> int:
    from mf.forecast.pipeline import plan_requests, uncached_questions, forecast
    from mf.retrieval.pipeline import load_evidence
    from mf.runtime import make_ctx

    arm_t = ARM_SETS[arms]
    ctx = make_ctx(prefix=f"bt-forecast-{split}", max_usd=max_usd, allow_spend=allow_spend and not dry_run)
    s = ctx.s
    qs, want_ret, want_noret = _split_sets(split, arm_t)
    if limit:
        qs = qs[:limit]
    plan = plan_requests(qs, s, load_evidence(s.run_dir), want_ret, want_noret)
    unc = uncached_questions(plan, ctx.llm)
    batch = s.pipeline.use_batch_api if use_batch is None else use_batch
    if dry_run:
        reqs = [r for d in plan.values() for rs in d.values() for r in rs if not ctx.llm.is_cached(r)]
        est = sum(ctx.llm.estimate(r, batch=batch) for r in reqs)
        log(f"DRY RUN forecast split={split} arms={arms} questions={len(plan)} uncached_questions={len(unc)}")
        log(f"  reasoner requests to make: {len(reqs)} (batch={batch}); PROJECTED anthropic ${est:.4f} "
            f"(pessimistic: full max_tokens), supervisor extra not included")
        log(f"  network calls made: {ctx.llm.network_calls + ctx.exa.network_calls}")
        return 0
    if not _pilot_gate(len(unc), ctx, log):
        return 3
    stats = forecast(qs, ctx, want_ret, want_noret, "supervisor" in arm_t, batch, log)
    log(f"forecast stats: {stats}")
    log(f"spent this run: ${ctx.budget.run_spent():.4f}; anthropic total ${ctx.budget.spent('anthropic'):.4f}")
    return 0


def pilot_cmd(n: int, allow_spend: bool, max_usd: float | None, log=print) -> int:
    """Full pipeline (sync) on the first n dev questions; measure $/question; project the backtest."""
    import json
    from collections import defaultdict

    from mf.core import timeutil
    from mf.forecast.pipeline import forecast
    from mf.retrieval.pipeline import retrieve_question, write_results
    from mf.runtime import make_ctx

    ctx = make_ctx(prefix="bt-pilot", max_usd=max_usd if max_usd is not None else 3.0, allow_spend=allow_spend)
    s = ctx.s
    qs = load_split("dev")[:n]
    # Pilot runs the no-retrieval arm on the dev pilot questions too, purely to measure its cost.
    pilot_qs = [q.model_copy(update={"split": "test"}) for q in qs]
    results = [retrieve_question(q, ctx.llm, ctx.exa, s) for q in qs]
    write_results(s.run_dir, results)
    kept = [len(r.kept) for r in results]
    n_results = [r.n_results for r in results]
    stats = forecast(pilot_qs, ctx, {"test"}, {"test"}, True, use_batch=False, log=log)
    # The pilot wrote rows with split=test labels; that only affects which arms ran, not the rows.
    by_op = defaultdict(float)
    for op, cost, _ in ctx.llm.cost_log + ctx.exa.cost_log:
        by_op[op] += cost
    per_q = {k: v / len(qs) for k, v in by_op.items()}
    retr_anth = per_q.get("query_gen", 0) + (by_op["relevance_summary"] / len(qs))
    exa_q = sum(v for k, v in per_q.items() if k.startswith("search_"))
    reason_sync = per_q.get("reason", 0)
    noret_sync = per_q.get("reason_noret", 0)
    sup_anth = per_q.get("supervisor_disagree", 0) + per_q.get("supervisor_update", 0)
    # supervisor's helper relevance calls are inside relevance_summary already (counted per question)
    ds = s.dataset
    n_main, n_test, n_canary = ds.n_total, ds.n_total - ds.n_dev, ds.n_canary
    proj_anth = (n_main * (retr_anth + sup_anth) + n_main * reason_sync * 0.5
                 + (n_test + n_canary) * noret_sync * 0.5)
    proj_exa = n_main * exa_q
    caps_anth = s.budget.anthropic_backtest_usd - ctx.budget.spent("anthropic", backtest_only=True)
    month = timeutil.month_key(timeutil.now())
    caps_exa = s.budget.exa_monthly_usd - ctx.budget.spent("exa", month=month)
    out = {
        "created_utc": timeutil.iso(timeutil.now()), "n_questions": len(qs),
        "usd_by_op_per_question_sync": {k: round(v, 6) for k, v in sorted(per_q.items())},
        "usd_per_question_sync_total": round(sum(per_q.values()), 6),
        "anthropic_usd_per_question_batch": round(retr_anth + sup_anth + reason_sync * 0.5 + noret_sync * 0.5, 6),
        "supervisor_trigger_rate": round(stats.get("supervisor_triggered", 0) / len(qs), 3),
        "kept_evidence_per_question": kept, "exa_results_per_question": n_results,
        "projected_backtest_anthropic_usd": round(proj_anth, 4), "projected_backtest_exa_usd": round(proj_exa, 4),
        "remaining_anthropic_backtest_usd": round(caps_anth, 4), f"remaining_exa_{month}_usd": round(caps_exa, 4),
        "forecast_stats": stats,
    }
    (s.state_dir).mkdir(parents=True, exist_ok=True)
    (s.state_dir / "pilot.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    log(json.dumps(out, indent=2))
    log(f"PROJECTED backtest: ${proj_anth:.2f} anthropic, ${proj_exa:.2f} exa "
        f"(remaining: ${caps_anth:.2f} anthropic backtest, ${caps_exa:.2f} exa this month)")
    if proj_anth > caps_anth or proj_exa > caps_exa:
        log("PILOT: projection EXCEEDS caps -> apply fallback levers (PLAN.md §11) before the backtest")
        return 4
    log("PILOT: projection within caps")
    return 0


# ---------------------------------------------------------------------------------------------
# live
# ---------------------------------------------------------------------------------------------
def _fake_responder(params) -> str:
    import hashlib
    import json as _j
    import re as _re

    u = params["messages"][0]["content"]
    h = int(hashlib.sha256(u.encode()).hexdigest()[:6], 16)
    if "search queries" in u:
        return '["latest developments", "historical precedent"]'
    if "Excerpts:" in u:
        idxs = [int(x) for x in _re.findall(r"^\[(\d+)\]", u, flags=_re.M)]
        return _j.dumps([{"idx": i, "relevance": 5, "mentions_events_after_t0": False, "reveals_outcome": False,
                          "summary": "Synthetic summary (dry run)."} for i in idxs])
    if "disagreements that explain" in u:
        return '{"disagreements": ["timing"], "queries": ["timing of decision"]}'
    if '"confidence"' in u:
        return '{"probability": 0.35, "confidence": "medium", "reason": "dry run"}'
    return f"Dry-run rationale.\nFINAL PROBABILITY: {0.2 + (h % 50) / 100:.2f}"


def live_cmd(n: int, dry_run: bool, allow_spend: bool, max_usd: float | None, log=print) -> int:
    import json as _j
    import tempfile
    from datetime import timedelta
    from pathlib import Path

    import httpx

    from mf.config import settings
    from mf.core import timeutil
    from mf.core.budget import BudgetGuard
    from mf.core.cache import Cache
    from mf.data import polymarket as P
    from mf.live import ledger as L
    from mf.live.run import forecast_one, run_live
    from mf.live.select import poly_live_price
    from mf.llm.client import CachedLLM, FakeLLM
    from mf.retrieval.exa_client import ExaClient
    from mf.runtime import Ctx, make_ctx

    s = settings()
    if dry_run:
        tmp = Path(tempfile.mkdtemp(prefix="mf-live-dry-"))
        cache = Cache(tmp / "cache", mode="readwrite")
        budget = BudgetGuard(tmp / "ledger_spend.jsonl", s.budget, run_id="live-dryrun", max_usd=1.0)
        exa_fx = _j.loads((s.root / "tests/fixtures/exa/search_synthetic.json").read_text(encoding="utf-8"))
        exa_fx["results"][0]["publishedDate"] = timeutil.iso(timeutil.now()).replace("Z", ".000Z")
        exa = ExaClient(cache, budget, http=httpx.Client(transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json=exa_fx))))
        ctx = Ctx(s, cache, budget, CachedLLM(FakeLLM(_fake_responder), cache, budget), exa, "live-dryrun", False)
        ev = _j.loads((s.root / "tests/fixtures/polymarket/event_negrisk.json").read_text(encoding="utf-8"))
        now = timeutil.now()
        qs = []
        for m in ev["markets"][:n]:
            pr = poly_live_price(m) or (0.5, "last_trade")
            qs.append(Question(qid=f"poly:{m['id']}", venue="polymarket", event_id=f"poly:{ev['id']}",
                               title=m["question"], description=P.sanitize_description(m.get("description") or ""),
                               category=P.classify(ev) or "World", created_at=now, t0=now,
                               scheduled_close=now + timedelta(days=30),
                               resolved_at=now + timedelta(days=30), horizon_days=30.0,
                               p_mkt_t0=min(max(pr[0], 0.03), 0.97), p_mkt_source=pr[1], volume=1.0, outcome=-1,
                               split="live", source_url="fixture"))
        ledger = tmp / "forecasts.jsonl"
        for q in qs:
            rec = L.append(ledger, forecast_one(q, ctx, w=0.4, log=log))
            log(f"[live dry-run] seq={rec.seq} {rec.qid} p_mkt={rec.p_mkt_at_forecast} halawi={rec.p_halawi} "
                f"aia={rec.p_aia} aia+mkt={rec.p_aia_market_ens} hash={rec.hash[:8]}")
        v = L.verify(ledger)
        log(f"[live dry-run] temp ledger {'OK' if v.ok else 'BROKEN'} n={v.n} head={v.head}; "
            f"network calls: llm={ctx.llm.network_calls} (fake) exa={ctx.exa.network_calls} (mocked); real ledger untouched")
        return 0 if v.ok else 1
    if not allow_spend:
        log("live mode makes paid calls; pass --allow-spend (or --dry-run)")
        return 2
    ctx = make_ctx(prefix="live", max_usd=max_usd, allow_spend=True)
    recs = run_live(n, ctx, s.data_dir / "live" / "forecasts.jsonl", log)
    v = L.verify(s.data_dir / "live" / "forecasts.jsonl")
    log(f"LEDGER {'OK' if v.ok else 'BROKEN'} n={v.n} head={v.head}")
    log(f"spent this run: ${ctx.budget.run_spent():.4f}")
    log(f"commit with: git add data/live && git commit -m \"live: {timeutil.now():%Y-%m-%d} n={len(recs)} head={v.head[:8]}\"")
    return 0 if v.ok else 1
