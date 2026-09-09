"""P2-4 claim 状态机 + verify 回查收口 集成探针（detail §7.6/§8.4，T-3.4 E-7/E-8）。
容器内 `docker exec obs-backend python /app/tests/integration/claim_probe.py` 运行。

形态 = HTTP 级真库（仿 pull_probe）：探针自建 async engine + `create_app(Settings(app_env=test,
evaluator_service_secret=…))` + `dependency_overrides[get_session]` 挂真库 → httpx
ASGITransport 全 HTTP 打端点（真实 JWT 鉴权 / 状态码 / 错误体）。回查判定（judge_link）直连
引擎 session，**offline 读面 = 探针内 httpx MockTransport 假 offline**（各场景 canned 数据，
走真实 offline_client 参数构造 + Bearer）——验证判据 wiring + uk_verify_run 幂等 + unclean
batch 落库 + CAS 收口。E-7/E-8 真 offline 端到端留阶段 4 环 2。

覆盖：
  C-1  claim：fix_version trim + k 固化 + claimed_by/due≈now+14d + conv(claim) + k 缺省=2
  C-2  ignore / reopen / admin fixed-review(approve±) / viewer→fixed-review 403
  C-3  E-7：假 offline 两版纯净 pass → verify_run_record×2 + verify passed + cluster fixed
       (closed_by=auto_regression conv)
  C-4  回归 fail → link verify failed + cluster 回退 open（conv reopen）
  C-5  run 环境级 na 且 case pass → unclean_batch 建批（uk_batch_agg）+ cluster 保持 claim
  C-6  双 cluster 同批（同 run+agent+version+error_type）+ resolve → 逐 reopened + 批 resolved
       （含 resolved_ts）+ link superseded 释放 cur_key；escalate 子校验：批 resolved(escalated)
       不迁移 cluster（保持 claim/link pending，§8.4 动作集）；re-entry 子校验：resolve 后同 key
       复发 → 复用同批重开（uk 幂等单行，不插重 / 无 IntegrityError 卡死）
  C-7  单 case na → cluster needs_review(reason=na) + link superseded + resolve reopen → open
  C-8  E-8：claim_due_ts 超窗 → claim_ttl_job 回退 open + fix_version 溯源 + conv(claim_ttl_expire)
  C-9  gen>1 claim（reentry 软提示；offline 未配 = warning None，claim 放行）
  C-10 CAS 竞态：双 session 同读 open → 先手 200 / 后到者 ERR_CLUSTER_0002(409)
  C-11 读面 3 GET：overview 形状 / clusters 筛选分页 / clusters/{id} 详情 verify_runs 时间线
  C-12 excluded_case_ids 命中 → record excluded_hit + case_pass NULL + 不迁移（保持 claim/pending）
  C-13 recheck_job 编排：驱动真 worker _run_recheck_cycle 扫 claim+pending → 逐簇独立事务收口
       fixed_auto（C-3 是 judge_link 直连单簇，本场景补编排路径 wiring）

隔离：agent 前缀 clm-%（≤64）；结尾清理 conv/link/verify_record/cluster/batch/user/
dict_config/agent。退出码全绿 0。
"""
import asyncio
import hashlib
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app")

import httpx  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import delete, select, update  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.backflow import batches as batch_flow  # noqa: E402
from app.backflow import claim as claim_flow  # noqa: E402
from app.backflow.verify import judge_link  # noqa: E402
from app.converter.envelope import assemble_cluster  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.core.db import get_session  # noqa: E402
from app.core.errors import AppError  # noqa: E402
from app.core.offline_client import OfflineClient  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.agent import Agent  # noqa: E402
from app.models.config import DictConfig  # noqa: E402
from app.models.error_flow import (  # noqa: E402
    ConversionRecord,
    ErrorCaseLink,
    ErrorCluster,
    NeedsReviewBatch,
    VerifyRunRecord,
)
from app.models.user import User  # noqa: E402
from app.worker.claim_ttl_job import run_claim_ttl  # noqa: E402

FAILURES: list[str] = []
IFACE = "GET /api/probe/clm"
_MOCK_SECRET = "probe-claim-secret"
_JWT = "probe-jwt-0123456789abcdefghijklmnopqrstuvwxyz"
ADMIN = "clm-probe-admin"
VIEWER = "clm-viewer"
API = "/api/v1"


def _aware_now() -> datetime:
    return datetime.now(timezone.utc)


def check(name: str, ok: bool, detail: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    if not ok:
        FAILURES.append(name)


# ---------- DB 基建 ----------


async def _cleanup(engine) -> None:
    """清 clm-% 残留（顺序防外键）：verify_record→link→conv→cluster + batch + user + dc→agent。"""
    async with AsyncSession(engine) as s:
        csub = select(ErrorCluster.id).where(ErrorCluster.agent.like("clm-%"))
        lsub = select(ErrorCaseLink.id).where(ErrorCaseLink.cluster_id.in_(csub))
        await s.execute(delete(VerifyRunRecord).where(VerifyRunRecord.link_id.in_(lsub)))
        await s.execute(delete(ErrorCaseLink).where(ErrorCaseLink.cluster_id.in_(csub)))
        await s.execute(delete(ConversionRecord).where(ConversionRecord.cluster_id.in_(csub)))
        await s.execute(delete(ErrorCluster).where(ErrorCluster.agent.like("clm-%")))
        await s.execute(delete(NeedsReviewBatch).where(NeedsReviewBatch.agent.like("clm-%")))
        await s.execute(delete(User).where(User.username.in_((ADMIN, VIEWER))))
        ag = select(Agent.id).where(Agent.name.like("clm-%"))
        await s.execute(delete(DictConfig).where(DictConfig.agent_id.in_(ag)))
        await s.execute(delete(Agent).where(Agent.name.like("clm-%")))
        await s.commit()


async def _ensure_user(engine, name: str, role: str) -> int:
    async with AsyncSession(engine) as s:
        u = User(username=name, password_hash="x" * 60, role=role, status=1)
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
        return uid


async def _seed_agent(engine, name: str) -> None:
    async with AsyncSession(engine) as s:
        s.add(Agent(name=name, display_name=name, base_url=None, enable=1,
                    route_source="auto_register", backflow_allow=1))
        await s.commit()


async def _seed_cluster(engine, agent: str, snapshot: str, *, gen: int = 1) -> int:
    """落 open cluster；input_hash 由 agent|snapshot 派生（同 agent 多簇不撞 uk_cluster_dedup）。"""
    input_hash = hashlib.sha256(f"{agent}|{snapshot}".encode()).hexdigest()
    async with AsyncSession(engine) as s:
        row = ErrorCluster(
            agent=agent, interface=IFACE, layer="L1", error_type="llm_timeout",
            input_hash=input_hash, input_snapshot=snapshot, input_truncated=0,
            error_msg="provider timeout", first_trace_id=f"clm-{agent}-1",
            trigger_version="2026.09.09-r1", fix_version=None,
            first_ts=datetime.now(), latest_ts=datetime.now(), count=1,
            generation=gen, status="open",
        )
        s.add(row)
        await s.flush()
        cid = row.id
        await s.commit()
        return cid


async def _activate(engine, cluster_id: int, case_id: str) -> int:
    """open cluster → assemble 现行 link → 置 active + case_id（模拟 offline ack active）。"""
    async with AsyncSession(engine) as s:
        cluster = (await s.scalars(
            select(ErrorCluster).where(ErrorCluster.id == cluster_id))).one()
        await assemble_cluster(s, cluster)
        link = (await s.scalars(
            select(ErrorCaseLink).where(ErrorCaseLink.cluster_id == cluster_id))).one()
        link.offline_status = "active"
        link.case_id = case_id
        lid = link.id
        await s.commit()
        return lid


async def _claim_cluster(engine, client, viewer_token, *, agent, snapshot, fv,
                         case_id=None, k=None, gen=1) -> int:
    """seed agent+cluster（可选 activate）→ HTTP claim → 返回 cluster_id（claim 200 前置）。"""
    await _seed_agent(engine, agent)
    cid = await _seed_cluster(engine, agent, snapshot, gen=gen)
    if case_id:
        await _activate(engine, cid, case_id)
    body = {"fix_version": fv, **({"k": k} if k is not None else {})}
    status, resp = await _post(client, f"clusters/{cid}/claim", viewer_token, body)
    assert status == 200, f"claim 前置失败 {agent}: {status} {resp}"
    return cid


async def _cluster(engine, cid: int) -> ErrorCluster | None:
    async with AsyncSession(engine) as s:
        return await s.get(ErrorCluster, cid)


async def _pending_link(engine, cid: int) -> ErrorCaseLink | None:
    async with AsyncSession(engine) as s:
        return (await s.scalars(
            select(ErrorCaseLink).where(ErrorCaseLink.cluster_id == cid,
                                        ErrorCaseLink.verify_status == "pending")
        )).first()


async def _conv_actions(engine, cid: int) -> list[str]:
    async with AsyncSession(engine) as s:
        return list((await s.scalars(
            select(ConversionRecord.action).where(ConversionRecord.cluster_id == cid)
        )).all())


async def _conv_closed(engine, cid: int, action: str):
    """取某动作 conv（closed_by 断言用）。"""
    async with AsyncSession(engine) as s:
        return (await s.scalars(
            select(ConversionRecord).where(ConversionRecord.cluster_id == cid,
                                           ConversionRecord.action == action)
        )).first()


async def _records(engine, link_id: int) -> list[VerifyRunRecord]:
    async with AsyncSession(engine) as s:
        return list((await s.scalars(
            select(VerifyRunRecord).where(VerifyRunRecord.link_id == link_id)
        )).all())


# ---------- HTTP 壳 ----------


def _hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _post(client, path, token, body=None):
    r = await client.post(f"{API}/backflow/{path}", json=body or {},
                          headers=_hdr(token))
    return r.status_code, r.json()


async def _get(client, path, token):
    r = await client.get(f"{API}/backflow/{path}", headers=_hdr(token))
    return r.status_code, r.json()


# ---------- 假 offline（MockTransport canned 数据；走真实 offline_client 参数构造） ----------


def _fake_offline(*, versions: list[str], by_version: dict, results: dict) -> OfflineClient:
    """离线读面 stub：list_runs 按 version 返回 runs；run_results 按 run_id 返回 rows。"""
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        params = dict(request.url.params)
        if path.endswith("/versions"):
            return httpx.Response(200, json={"versions": [{"version": v} for v in versions]})
        if path == "/api/v1/runs":
            return httpx.Response(200, json={"runs": by_version.get(params.get("version"), [])})
        run_id = path.split("/runs/")[1].split("/results")[0]
        return httpx.Response(200, json={"rows": results.get(run_id, [])})

    return OfflineClient("http://offline-fake", secret=_MOCK_SECRET, timeout_s=3,
                         transport=httpx.MockTransport(handler))


def _run_item(run_id: str, *, na_error_types=None, excluded_case_ids=None) -> dict:
    return {"run_id": run_id, "status": "completed",
            "na_error_types": na_error_types or [],
            "excluded_case_ids": excluded_case_ids or []}


def _case_row(case_id: str, run_id: str, *, x_pf: str, error_type=None) -> dict:
    return {"case_id": case_id, "run_id": run_id, "pass_fail": x_pf,
            "error_type": error_type}


async def _run_judge(engine, fake: OfflineClient, cid: int) -> dict:
    """judge_link 单 cluster 回查（独立事务 commit；复用真判定内核）。"""
    async with AsyncSession(engine) as s2:
        cluster = (await s2.scalars(
            select(ErrorCluster).where(ErrorCluster.id == cid))).one()
        link = (await s2.scalars(
            select(ErrorCaseLink).where(ErrorCaseLink.cluster_id == cid,
                                        ErrorCaseLink.verify_status == "pending")
        )).first()
        summary = await judge_link(s2, fake, cluster=cluster, link=link)
        await s2.commit()
        return summary


# ---------- C 场景 ----------


async def c1_claim_fields(engine, client, viewer_token, viewer_id) -> None:
    print("\n===== C-1 claim：字段固化 + k 缺省 + conv =====")
    await _seed_agent(engine, "clm-c1")
    cid = await _seed_cluster(engine, "clm-c1", '{"q": "c1-a"}')
    status, body = await _post(client, f"clusters/{cid}/claim", viewer_token,
                               {"fix_version": "  1.4.0  ", "k": 2, "note": "排障"})
    c = await _cluster(engine, cid)
    due = datetime.fromisoformat(body["claim_due_ts"].replace("Z", "+00:00"))
    delta = due - _aware_now()
    ok = (status == 200 and body["fix_version"] == "1.4.0" and body["claim_k"] == 2
          and c.status == "claim" and c.fix_version == "1.4.0"  # trim 归一
          and c.claim_k == 2 and c.claimed_by == viewer_id
          and timedelta(days=13) < delta < timedelta(days=15))
    check("C-1 claim：fix_version trim + k=2 固化 + claimed_by=viewer + due≈now+14d",
          ok, f"{status} fix={c.fix_version} k={c.claim_k} by={c.claimed_by} due≈{delta.days}d")
    check("C-1 conv(action=claim) 落库", "claim" in await _conv_actions(engine, cid),
          f"{await _conv_actions(engine, cid)}")
    # k 缺省 → dict_config auto_fixed_k_default（缺省 2）写死固化
    cid2 = await _seed_cluster(engine, "clm-c1", '{"q": "c1-b"}')
    s2, b2 = await _post(client, f"clusters/{cid2}/claim", viewer_token,
                         {"fix_version": "1.5.0"})
    check("C-1 k 缺省 → auto_fixed_k_default=2 固化",
          s2 == 200 and b2["claim_k"] == 2, f"{s2} {b2}")


async def c2_state_transitions(engine, client, viewer_token, admin_token) -> None:
    print("\n===== C-2 ignore/reopen/fixed-review + admin-only =====")
    await _seed_agent(engine, "clm-c2")
    # viewer → fixed-review 403（admin-only，角色守卫先于状态守卫）
    v_cid = await _seed_cluster(engine, "clm-c2", '{"q": "c2-v"}')
    s, b = await _post(client, f"clusters/{v_cid}/fixed-review", viewer_token, {"approve": True})
    check("C-2 viewer 调 fixed-review → ERR_AUTH_0002(403)",
          s == 403 and b["code"] == "ERR_AUTH_0002", f"{s} {b}")
    # ignore open→inactive + conv；reopen inactive→open + conv
    ig = await _seed_cluster(engine, "clm-c2", '{"q": "c2-ig"}')
    s, _ = await _post(client, f"clusters/{ig}/ignore", viewer_token)
    c_ig = await _cluster(engine, ig)
    check("C-2 ignore open→inactive + conv(ignore)",
          s == 200 and c_ig.status == "inactive"
          and "ignore" in await _conv_actions(engine, ig), f"{s} {c_ig.status}")
    s, _ = await _post(client, f"clusters/{ig}/reopen", viewer_token, {"note": "反悔"})
    check("C-2 reopen inactive→open + conv(reopen)",
          s == 200 and (await _cluster(engine, ig)).status == "open"
          and "reopen" in await _conv_actions(engine, ig), f"{s}")
    # admin fixed-review approve:true → fixed(closed_by=admin_review)
    fx = await _seed_cluster(engine, "clm-c2", '{"q": "c2-fx"}')
    assert (await _post(client, f"clusters/{fx}/claim", viewer_token,
                        {"fix_version": "2.1.0"}))[0] == 200
    s, _ = await _post(client, f"clusters/{fx}/fixed-review", admin_token, {"approve": True})
    conv = await _conv_closed(engine, fx, "fixed_review")
    c_fx = await _cluster(engine, fx)
    check("C-2 admin approve → fixed + conv(closed_by=admin_review)",
          s == 200 and c_fx.status == "fixed" and conv is not None
          and conv.closed_by == "admin_review", f"{s} {c_fx.status}")
    # approve:false → claim→open（=reopen 语义）
    rj = await _seed_cluster(engine, "clm-c2", '{"q": "c2-rj"}')
    assert (await _post(client, f"clusters/{rj}/claim", viewer_token,
                        {"fix_version": "2.2.0"}))[0] == 200
    s, _ = await _post(client, f"clusters/{rj}/fixed-review", admin_token, {"approve": False})
    check("C-2 fixed-review approve:false → claim→open",
          s == 200 and (await _cluster(engine, rj)).status == "open", f"{s}")


async def c3_verify_passed_e7(engine, client, viewer_token) -> None:
    print("\n===== C-3 E-7：两版纯净 pass → verify_run_record×2 + passed + cluster fixed =====")
    cid = await _claim_cluster(engine, client, viewer_token, agent="clm-c3",
                               snapshot='{"q": "c3"}', fv="3.0.0", case_id="case-c3", k=2)
    link = await _pending_link(engine, cid)
    fake = _fake_offline(
        versions=["3.0.0", "3.1.0"],
        by_version={"3.0.0": [_run_item("c3r1")], "3.1.0": [_run_item("c3r2")]},
        results={"c3r1": [_case_row("case-c3", "c3r1", x_pf="pass")],
                 "c3r2": [_case_row("case-c3", "c3r2", x_pf="pass")]},
    )
    try:
        summary = await _run_judge(engine, fake, cid)
        recs = await _records(engine, link.id)
        c = await _cluster(engine, cid)
        conv = await _conv_closed(engine, cid, "auto_fixed")
        after_link = await _pending_link(engine, cid)
        ok = (summary["outcome"] == "fixed_auto"
              and c.status == "fixed"
              and after_link is None  # pending → passed（不再现行）
              and conv is not None and conv.closed_by == "auto_regression"
              and len(recs) == 2 and all(r.case_pass == 1 for r in recs))
        check("C-3 E-7：verify_run_record×2 + verify passed + fixed(closed_by=auto_regression)",
              ok, f"{summary} status={c.status} records={len(recs)}")
    finally:
        await fake.aclose()


async def c4_fail_reopen(engine, client, viewer_token) -> None:
    print("\n===== C-4 回归 fail → verify failed + cluster 回退 open =====")
    cid = await _claim_cluster(engine, client, viewer_token, agent="clm-c4",
                               snapshot='{"q": "c4"}', fv="4.0.0", case_id="case-c4", k=2)
    link = await _pending_link(engine, cid)
    fake = _fake_offline(
        versions=["4.0.0"],
        by_version={"4.0.0": [_run_item("c4r1")]},
        results={"c4r1": [_case_row("case-c4", "c4r1", x_pf="fail",
                                    error_type="assertion_shape")]},
    )
    try:
        summary = await _run_judge(engine, fake, cid)
        c = await _cluster(engine, cid)
        recs = await _records(engine, link.id)
        ok = (summary["outcome"] == "reopened"
              and c.status == "open"
              and "reopen" in await _conv_actions(engine, cid)
              and len(recs) == 1 and recs[0].case_pass == 0)
        check("C-4 fail → cluster open + record case_pass=0 + conv(reopen)", ok,
              f"{summary} status={c.status}")
    finally:
        await fake.aclose()


async def c5_unclean_batch(engine, client, viewer_token) -> None:
    print("\n===== C-5 环境级 na run + case pass → unclean_batch（cluster 保持 claim） =====")
    cid = await _claim_cluster(engine, client, viewer_token, agent="clm-c5",
                               snapshot='{"q": "c5"}', fv="5.0.0", case_id="case-c5", k=2)
    fake = _fake_offline(
        versions=["5.0.0"],
        by_version={"5.0.0": [_run_item("c5r1", na_error_types=["circuit_open"])]},
        results={"c5r1": [_case_row("case-c5", "c5r1", x_pf="pass")]},
    )
    try:
        summary = await _run_judge(engine, fake, cid)
        c = await _cluster(engine, cid)
        link = await _pending_link(engine, cid)
        async with AsyncSession(engine) as s:
            batch = (await s.scalars(
                select(NeedsReviewBatch).where(NeedsReviewBatch.run_id == "c5r1")
            )).first()
        ok = (summary["outcome"] == "unclean_batch"
              and batch is not None and batch.status == "open"
              and batch.error_type == "circuit_open"
              and c.status == "claim" and link is not None)  # 批引 cluster 不入 needs_review
        check("C-5 unclean：批建(uk error_type=circuit_open) + cluster 保持 claim + link 不动",
              ok, f"{summary} batch={batch.id if batch else None}")
    finally:
        await fake.aclose()


async def c6_batch_resolve(engine, client, viewer_token) -> None:
    print("\n===== C-6 双 cluster 同批 unclean + resolve → 整批 reopened + 批 resolved =====")
    agent = "clm-c6"
    await _seed_agent(engine, agent)
    cids = []
    for tag in ("a", "b"):
        cid = await _seed_cluster(engine, agent, '{"q": "c6-%s"}' % tag)
        await _activate(engine, cid, f"case-c6{tag}")
        s, b = await _post(client, f"clusters/{cid}/claim", viewer_token,
                           {"fix_version": "6.0.0"})
        assert s == 200, f"c6 claim {tag} 失败: {b}"
        cids.append(cid)
    fake = _fake_offline(
        versions=["6.0.0"],
        by_version={"6.0.0": [_run_item("c6run", na_error_types=["pool_error"])]},
        results={"c6run": [_case_row("case-c6a", "c6run", x_pf="pass"),
                           _case_row("case-c6b", "c6run", x_pf="pass")]},
    )
    try:
        s1 = await _run_judge(engine, fake, cids[0])
        s2 = await _run_judge(engine, fake, cids[1])
        async with AsyncSession(engine) as s:
            batch = (await s.scalars(
                select(NeedsReviewBatch).where(NeedsReviewBatch.run_id == "c6run")
            )).one()
        refs = list(batch.link_refs)
        codes, body = await _post(client, f"needs-review-batches/{batch.id}/resolve",
                                  viewer_token, {"action": "reopen_cluster"})
        statuses = {x["cluster_id"]: x["status"] for x in body.get("results", [])}
        ok = (s1["outcome"] == "unclean_batch" and s2["outcome"] == "unclean_batch"
              and len(refs) == 2 and batch.status == "open"
              and codes == 200 and len(statuses) == 2
              and all(statuses[c] == "reopened" for c in cids))
        async with AsyncSession(engine) as s3:
            b3 = (await s3.scalars(
                select(NeedsReviewBatch).where(NeedsReviewBatch.id == batch.id))).one()
            links = list((await s3.scalars(
                select(ErrorCaseLink).where(ErrorCaseLink.cluster_id.in_(cids))
            )).all())
        # await 不能嵌 genexp（会成 async_generator）——先物化再断言
        open_after = []
        conv_after = []
        for c in cids:
            open_after.append((await _cluster(engine, c)).status)
            conv_after.append(await _conv_actions(engine, c))
        ok2 = (b3.status == "resolved" and b3.resolved_ts is not None
               and all(s == "open" for s in open_after)
               and all(lk.verify_status == "superseded" and lk.cur_key is None
                       for lk in links)
               and all("needs_review_resolve" in acts for acts in conv_after))
        check("C-6 同批 2 ref + resolve 整批 reopened + 批 resolved(含 resolved_ts)",
              ok and ok2, f"{s1}/{s2} refs={len(refs)} results={statuses}")
        # ---- escalate 子校验（§8.4 动作集）：批置 resolved 不迁移 cluster，link 保持 pending ----
        cids2 = []
        for tag in ("c", "d"):
            cid2 = await _seed_cluster(engine, agent, '{"q": "c6-escalate-%s"}' % tag)
            await _activate(engine, cid2, f"case-c6e{tag}")
            s, b = await _post(client, f"clusters/{cid2}/claim", viewer_token,
                               {"fix_version": "6.0.0"})
            assert s == 200, f"c6 escalate claim {tag} 失败: {b}"
            cids2.append(cid2)
        fake2 = _fake_offline(
            versions=["6.0.0"],
            by_version={"6.0.0": [_run_item("c6run2", na_error_types=["pool_error"])]},
            results={"c6run2": [_case_row("case-c6ec", "c6run2", x_pf="pass"),
                                _case_row("case-c6ed", "c6run2", x_pf="pass")]},
        )
        try:
            for c2 in cids2:
                await _run_judge(engine, fake2, c2)
            async with AsyncSession(engine) as s4:
                batch2 = (await s4.scalars(
                    select(NeedsReviewBatch).where(NeedsReviewBatch.run_id == "c6run2")
                )).one()
            code2, body2 = await _post(
                client, f"needs-review-batches/{batch2.id}/resolve", viewer_token,
                {"action": "escalated", "note": "超时升级人工跟进"})
            st2 = {x["cluster_id"]: x["status"] for x in body2.get("results", [])}
            async with AsyncSession(engine) as s5:
                b5 = (await s5.scalars(
                    select(NeedsReviewBatch).where(NeedsReviewBatch.id == batch2.id))).one()
                link_st2 = list((await s5.scalars(
                    select(ErrorCaseLink).where(ErrorCaseLink.cluster_id.in_(cids2))
                )).all())
            ok3 = (code2 == 200 and body2.get("action") == "escalated"
                   and all(st2.get(c) == "claim" for c in cids2)
                   and b5.status == "resolved" and b5.resolve_action == "escalated"
                   and b5.resolved_ts is not None
                   and all(lk.verify_status == "pending" for lk in link_st2))
            check("C-6 escalate：批 resolved + cluster 保持 claim/link pending",
                  ok3, f"results={st2} resolve_action={b5.resolve_action}")
        finally:
            await fake2.aclose()
        # ---- resolve 后同 key 复发 → 复用同批重开（uk 单行，不插重防 IntegrityError） ----
        re_cid = await _seed_cluster(engine, agent, '{"q": "c6-reenter"}')
        async with AsyncSession(engine) as s6:
            reopened_id = await batch_flow.ensure_unclean_batch(
                s6, run_id="c6run", agent=agent, bound_version="6.0.0",
                error_type="pool_error", cluster_id=re_cid, link_id=0, case_id=None)
            await s6.commit()
            b6 = (await s6.scalars(
                select(NeedsReviewBatch).where(NeedsReviewBatch.id == reopened_id))).one()
            rows = list((await s6.scalars(
                select(NeedsReviewBatch).where(NeedsReviewBatch.run_id == "c6run"))).all())
        ok4 = (reopened_id == batch.id and b6.status == "open"
               and b6.resolve_action is None and b6.resolved_ts is None
               and len(rows) == 1  # uk 幂等：同 key 不产生第二条
               and any(int(r.get("cluster_id")) == re_cid for r in b6.link_refs))
        check("C-6 re-entry：resolve 后同 key 再现 → 复用同批重开（不插重/无 IntegrityError）",
              ok4, f"id={reopened_id} status={b6.status} rows={len(rows)} refs={len(b6.link_refs)}")
    finally:
        await fake.aclose()


async def c7_na_needs_review(engine, client, viewer_token) -> None:
    print("\n===== C-7 单 case na → needs_review(na) + superseded + resolve reopen =====")
    cid = await _claim_cluster(engine, client, viewer_token, agent="clm-c7",
                               snapshot='{"q": "c7"}', fv="7.0.0", case_id="case-c7", k=2)
    fake = _fake_offline(
        versions=["7.0.0"],
        by_version={"7.0.0": [_run_item("c7r1")]},
        results={"c7r1": [_case_row("case-c7", "c7r1", x_pf="na",
                                    error_type="timeout")]},
    )
    try:
        summary = await _run_judge(engine, fake, cid)
        c = await _cluster(engine, cid)
        ok = (summary["outcome"] == "needs_review"
              and c.status == "needs_review" and c.needs_review_reason == "na"
              and "needs_review" in await _conv_actions(engine, cid))
        check("C-7 na → cluster needs_review(reason=na) + conv(needs_review)", ok,
              f"{summary} reason={c.needs_review_reason}")
        async with AsyncSession(engine) as s:
            lk = (await s.scalars(select(ErrorCaseLink)
                                  .where(ErrorCaseLink.cluster_id == cid))).one()
        check("C-7 现行 link superseded + cur_key 释放",
              lk.verify_status == "superseded" and lk.cur_key is None,
              f"verify={lk.verify_status} cur_key={lk.cur_key}")
        s, b = await _post(client, f"clusters/{cid}/needs-review-resolve", viewer_token,
                           {"action": "reopen_cluster", "note": "确认可复测"})
        check("C-7 needs-review-resolve reopen_cluster → open + conv",
              s == 200 and b["status"] == "open"
              and "needs_review_resolve" in await _conv_actions(engine, cid), f"{s} {b}")
    finally:
        await fake.aclose()


async def c8_ttl_e8(engine, client, viewer_token) -> None:
    print("\n===== C-8 E-8：claim_due_ts 超窗 → claim_ttl_job 回退 open =====")
    cid = await _claim_cluster(engine, client, viewer_token, agent="clm-c8",
                               snapshot='{"q": "c8"}', fv="8.0.0", k=2)
    async with AsyncSession(engine) as s:
        await s.execute(update(ErrorCluster).where(ErrorCluster.id == cid)
                        .values(claim_due_ts=datetime.now() - timedelta(days=1)))
        await s.commit()
    expired = await run_claim_ttl(engine)
    c = await _cluster(engine, cid)
    conv = await _conv_closed(engine, cid, "claim_ttl_expire")
    ok = (expired >= 1 and c.status == "open"
          and c.claimed_by is None and c.claimed_at is None and c.claim_due_ts is None
          and c.fix_version == "8.0.0"  # 处置人选的修复版本保留溯源
          and conv is not None and "TTL" in (conv.detail or ""))
    check("C-8 E-8：超窗 → open + 处置字段清空 + fix_version 溯源 + conv(claim_ttl_expire)",
          ok, f"expired={expired} status={c.status} fix={c.fix_version}")


async def c9_reentry_soft(engine, client, viewer_token) -> None:
    print("\n===== C-9 gen>1 claim 软提示：offline 未配 = warning None（硬闸 P2-5） =====")
    await _seed_agent(engine, "clm-c9")
    cid = await _seed_cluster(engine, "clm-c9", '{"q": "c9"}', gen=2)
    s, b = await _post(client, f"clusters/{cid}/claim", viewer_token,
                       {"fix_version": "9.0.0", "note": "reentry 复现"})
    c = await _cluster(engine, cid)
    ok = (s == 200 and c.status == "claim" and c.claimed_by is not None
          and b.get("warning") is None)  # offline_base_url 空 → 软提示退 None，claim 放行
    check("C-9 gen>1 claim 放行 + warning=None（未配 offline）", ok,
          f"{s} status={c.status} warning={b.get('warning')}")


async def c10_cas_conflict(engine, viewer_id) -> None:
    print("\n===== C-10 CAS 竞态：双 session 同读 open → 后到者 ERR_CLUSTER_0002(409) =====")
    await _seed_agent(engine, "clm-c10")
    cid = await _seed_cluster(engine, "clm-c10", '{"q": "c10"}')
    conflict = None
    async with AsyncSession(engine) as sa:
        ca = (await sa.scalars(
            select(ErrorCluster).where(ErrorCluster.id == cid))).one()
        async with AsyncSession(engine) as sb:
            cb = (await sb.scalars(
                select(ErrorCluster).where(ErrorCluster.id == cid))).one()
            await claim_flow.claim_cluster(sa, ca, fix_version="10.0.0", note=None,
                                           k=2, actor_id=viewer_id)
            await sa.commit()
            try:
                await claim_flow.claim_cluster(sb, cb, fix_version="10.0.0", note=None,
                                               k=2, actor_id=viewer_id)
            except AppError as exc:
                conflict = exc
            await sb.rollback()
    c = await _cluster(engine, cid)
    ok = (c.status == "claim"
          and conflict is not None and conflict.http == 409
          and conflict.code == "ERR_CLUSTER_0002")
    check("C-10 先手 claim 成功 + 后到者 ERR_CLUSTER_0002(409)",
          ok, f"status={c.status} err={conflict.code if conflict else None}")


async def c11_read_api(engine, client, viewer_token, admin_token) -> None:
    print("\n===== C-11 读面 3 GET：overview / clusters 分页筛选 / 详情时间线 =====")
    s, b = await _get(client, "overview", viewer_token)
    ok = (s == 200
          and set(("clusters", "links", "to_fix", "by_agent")).issubset(b)
          and "claim" in b["clusters"] and "pending" in b["links"])
    check("C-11 overview 形状（clusters/links/to_fix/by_agent 计数）", ok,
          f"{s} keys={list(b)}")
    s, b = await _get(client, "clusters?agent=clm-c3&page=1&page_size=2", viewer_token)
    ok = (s == 200 and b["page"] == 1 and b["total"] == 1 and len(b["items"]) == 1
          and b["items"][0]["agent"] == "clm-c3"
          and b["items"][0]["status"] == "fixed"
          and isinstance(b["items"][0]["link"], dict))
    check("C-11 clusters 筛选 agent + 分页（item 含 link 摘要）", ok,
          f"{s} total={b.get('total')} items={len(b.get('items', []))}")
    async with AsyncSession(engine) as s3:
        c3 = (await s3.scalars(
            select(ErrorCluster).where(ErrorCluster.agent == "clm-c3"))).one()
    s, b = await _get(client, f"clusters/{c3.id}", viewer_token)
    ok = (s == 200 and "verify_runs" in b and "conversions" in b
          and "waiting_days" in b and len(b["verify_runs"]) == 2
          and any(x["action"] == "auto_fixed" for x in b["conversions"]))
    check("C-11 clusters/{id} 详情：verify_runs 时间线×2 + conversions 审计", ok,
          f"{s} verify={len(b.get('verify_runs', []))}")
    s2, _ = await _get(client, "overview", admin_token)
    check("C-11 admin 可读 overview（viewer 门槛含 admin）", s2 == 200, f"{s2}")


async def c12_excluded_diagnosis(engine, client, viewer_token) -> None:
    print("\n===== C-12 excluded_case_ids 命中 → 欠测标注 + 不自动迁移 =====")
    cid = await _claim_cluster(engine, client, viewer_token, agent="clm-c12",
                               snapshot='{"q": "c12"}', fv="12.0.0", case_id="case-c12", k=2)
    link = await _pending_link(engine, cid)
    fake = _fake_offline(
        versions=["12.0.0"],
        by_version={"12.0.0": [_run_item("c12r1", excluded_case_ids=["case-c12"])]},
        results={"c12r1": []},
    )
    try:
        summary = await _run_judge(engine, fake, cid)
        c = await _cluster(engine, cid)
        recs = await _records(engine, link.id)
        ok = (summary["outcome"] == "pending"
              and len(recs) == 1 and recs[0].case_pass is None
              and bool((recs[0].raw_json or {}).get("excluded_hit"))
              and c.status == "claim")
        check("C-12 excluded 命中：record excluded_hit + case_pass NULL + 保持 claim", ok,
              f"{summary} records={len(recs)} status={c.status}")
    finally:
        await fake.aclose()


async def c13_recheck_orchestration(engine, client, viewer_token) -> None:
    """C-13 recheck_job 编排：驱动真 worker _run_recheck_cycle（扫描/逐簇事务/计数）。

    与 C-3（judge_link 直连单簇）互补——本场景从 worker 函数入口进入，验 recheck_job
    scan→judge→commit 编排 wiring 通。置于 C-3 后执行：此刻 claim∧pending∧case 候选
    仅自身簇（早前场景要么无现行 pending link 要么已收口），counts 确定性 = fixed_auto。"""
    print("\n===== C-13 recheck_job 编排：_run_recheck_cycle 扫 claim+pending → 收口 =====")
    from app.worker.recheck_job import _run_recheck_cycle  # noqa: E402

    cid = await _claim_cluster(engine, client, viewer_token, agent="clm-c13",
                               snapshot='{"q": "c13"}', fv="13.0.0", case_id="case-c13", k=1)
    link = await _pending_link(engine, cid)
    fake = _fake_offline(
        versions=["13.0.0"],
        by_version={"13.0.0": [_run_item("c13r1")]},
        results={"c13r1": [_case_row("case-c13", "c13r1", x_pf="pass")]},
    )
    try:
        counts, total = await _run_recheck_cycle(engine, fake, batch=200)
        c = await _cluster(engine, cid)
        recs = await _records(engine, link.id)
        ok = (total >= 1 and counts.get("fixed_auto", 0) == 1
              and c.status == "fixed"
              and len(recs) == 1 and recs[0].case_pass == 1)
        check("C-13 recheck 编排：worker 路径 fixed_auto 收口（cluster fixed + record×1）",
              ok, f"counts={counts} total={total} status={c.status} records={len(recs)}")
    finally:
        await fake.aclose()


_settings_cache: dict = {}


def _app_settings() -> Settings:
    if "s" not in _settings_cache:
        _settings_cache["s"] = Settings(app_env="test", resource_env="dev",
                                        jwt_secret=_JWT, evaluator_service_secret=_MOCK_SECRET)
    return _settings_cache["s"]


async def main() -> None:
    db = Settings()  # 容器真 env（DB_HOST=mysql 等）
    engine = create_async_engine(db.sqlalchemy_url)
    app = create_app(_app_settings())
    app.state.settings = _app_settings()  # httpx ASGI 不拉起 lifespan，手动挂 settings

    async def _override_session():
        async with AsyncSession(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _override_session
    try:
        await _cleanup(engine)
        admin_id = await _ensure_user(engine, ADMIN, "admin")
        viewer_id = await _ensure_user(engine, VIEWER, "viewer")
        admin_token = create_access_token(_app_settings(), admin_id, "admin")
        viewer_token = create_access_token(_app_settings(), viewer_id, "viewer")
        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url="http://probe") as client:
            await c1_claim_fields(engine, client, viewer_token, viewer_id)
            await c2_state_transitions(engine, client, viewer_token, admin_token)
            await c3_verify_passed_e7(engine, client, viewer_token)
            await c13_recheck_orchestration(engine, client, viewer_token)
            await c4_fail_reopen(engine, client, viewer_token)
            await c5_unclean_batch(engine, client, viewer_token)
            await c6_batch_resolve(engine, client, viewer_token)
            await c7_na_needs_review(engine, client, viewer_token)
            await c8_ttl_e8(engine, client, viewer_token)
            await c9_reentry_soft(engine, client, viewer_token)
            await c10_cas_conflict(engine, viewer_id)
            await c11_read_api(engine, client, viewer_token, admin_token)
            await c12_excluded_diagnosis(engine, client, viewer_token)
    finally:
        await _cleanup(engine)
        await engine.dispose()
    print("\n===== claim_probe 结果 =====")
    if FAILURES:
        print(f"FAIL: {len(FAILURES)} 项失败 → {FAILURES}")
        sys.exit(1)
    print("全绿：P2-4 claim 状态机 + verify 回查收口 13 场景通过")


if __name__ == "__main__":
    asyncio.run(main())
