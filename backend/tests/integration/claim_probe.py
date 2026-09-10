"""P2-4 claim 状态机 + verify 判定收口 集成探针（detail §7.6/§8.4，T-3.4 E-7/E-8）。
**v1.23 第 3 刀起判定数据源 = 推送载荷**（轮询读面已删）。容器内运行：
`docker exec obs-backend python /app/tests/integration/claim_probe.py`。

形态 = HTTP 级真库（仿 pull_probe）：探针自建 async engine + `create_app(Settings(app_env=test,
evaluator_service_secret=…))` + `dependency_overrides[get_session]` 挂真库 → httpx
ASGITransport 全 HTTP 打端点（真实 JWT 鉴权 / 状态码 / 错误体）。
判定数据源（第 3 刀）：**已落库的 verify_run_record 行**（raw_json = 推送载荷原样留档）——
原「假 offline 读面」随轮询链整删；场景造数一律落**推送形态**的行（`_seed_run`/`_push_body`），
判定由直连 judge_link（`_run_judge`）或**推送端点**（`_push`，线上唯一写入路径）驱动。
验证判据 wiring + uk_verify_run 幂等 + unclean batch 落库 + CAS 收口 + 落库即判同事务。

覆盖：
  C-1  claim：fix_version trim + k 固化 + claimed_by/due≈now+14d + conv(claim) + k 缺省=2
  C-2  ignore / reopen / admin fixed-review(approve±) / viewer→fixed-review 403
  C-3  E-7：两版纯净 pass（行含 prev_terminal_version 链）→ verify_run_record×2 + verify
       passed + cluster fixed (closed_by=auto_regression conv)
  C-4  回归 fail → link verify failed + cluster 回退 open（conv reopen）
  C-5  同 run 环境级 na 行 + 本 case pass → unclean_batch 建批（uk_batch_agg）+ cluster 保持 claim
  C-6  双 cluster 同批（同 run+agent+version+error_type）+ resolve → 逐 reopened + 批 resolved
       （含 resolved_ts）+ link superseded 释放 cur_key；escalate 子校验：批 resolved(escalated)
       不迁移 cluster（保持 claim/link pending，§8.4 动作集）；re-entry 子校验：resolve 后同 key
       复发 → 复用同批重开（uk 幂等单行，不插重 / 无 IntegrityError 卡死）
  C-7  单 case na → cluster needs_review(reason=na) + link superseded + resolve reopen → open
  C-8  E-8：claim_due_ts 超窗 → claim_ttl_job 回退 open + fix_version 溯源 + conv(claim_ttl_expire)
  C-9  gen>1 claim（reentry 软提示；本地零已收结果 = warning None，claim 放行）
  C-10 CAS 竞态：双 session 同读 open → 先手 200 / 后到者 ERR_CLUSTER_0002(409)
  C-11 读面 3 GET：overview 形状 / clusters 筛选分页 / clusters/{id} 详情 verify_runs 时间线
  C-12 欠测（载荷 cases[] 不含本 link case_id）→ 详情读面 excluded_hit=True + case_pass NULL
       + 不迁移（保持 claim/pending）
  C-13 **推送端点编排**（原 recheck_job 编排的替代）：HTTP push → 落库 + 同事务判定 →
       fixed_auto 收口 + links_advanced=[link] 回执（C-3 是 judge_link 直连单簇，本场景补
       线上唯一写入路径的端到端 wiring）
  C-14 E-10（P2-5 S-11 归属）：passed/fixed 终态后再调 judge_link（link 已非 pending）→ 显式
       守卫 no_progress；迟到同版本 fail run 从推送端点进来 → 反查不到现行 pending link →
       落**哨兵孤儿行**（link_id=0）留痕，终态 link 时间线不追加不覆写（reentry 门控探针见
       cluster_probe S-7~S-10）
  C-15 **E-17（T-3.10 补）**：fail 回退 open → 改 fix_version 再 claim → 组装出**新 link + 新
      payload_id**（非复用旧 link）→ 新版本回归 passed → cluster fixed，且**旧 failed 的
      verify_run_record 时间线保留**。组装用新助手 `_assemble_new_link`（不复用 `_activate`：
      其取 link 用 `.one()` 且不筛 pending，旧终态 link 在场会 MultipleResultsFound）；
      **同时验缺行中断判据的 ≥fix_version 边界**：新行 prev_terminal_version=5.0.0（本地无该
      版本行，但 < 新 fv 5.1.0）→ 不得判 gap（否则 E-17 现场永久钉死）。

隔离：agent 前缀 clm-%（≤64）；结尾清理 conv/link/verify_record/cluster/batch/user/
dict_config/agent + 哨兵孤儿行。退出码全绿 0。
"""
import asyncio
import hashlib
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app")

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
# 探针产生的哨兵孤儿行 run_id（挂不到 cluster 子查询，见 _cleanup 注释）
_ORPHAN_RUN_IDS = ("c14r2",)


def _aware_now() -> datetime:
    return datetime.now(timezone.utc)


def check(name: str, ok: bool, detail: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    if not ok:
        FAILURES.append(name)


# ---------- DB 基建 ----------


async def _cleanup(engine) -> None:
    """清 clm-% 残留（顺序防外键）：verify_record→link→conv→cluster + batch + user + dc→agent。

    另清**哨兵孤儿行**：C-14 的迟到 run 反查不到现行 pending link → link_id=0，挂不到
    cluster 子查询上。按探针专属 run_id 前缀识别（`_ORPHAN_RUN_IDS`），**不按 link_id=0
    一刀切**（该哨兵位可能承载非探针的历史 orphan 数据，不能误删）。
    """
    async with AsyncSession(engine) as s:
        csub = select(ErrorCluster.id).where(ErrorCluster.agent.like("clm-%"))
        lsub = select(ErrorCaseLink.id).where(ErrorCaseLink.cluster_id.in_(csub))
        await s.execute(delete(VerifyRunRecord).where(VerifyRunRecord.link_id.in_(lsub)))
        await s.execute(delete(VerifyRunRecord).where(
            VerifyRunRecord.run_id.in_(_ORPHAN_RUN_IDS)))
        await s.execute(delete(ErrorCaseLink).where(ErrorCaseLink.cluster_id.in_(csub)))
        await s.execute(delete(ConversionRecord).where(ConversionRecord.cluster_id.in_(csub)))
        for rid in _ORPHAN_RUN_IDS:  # 孤儿 conv：cluster_id=NULL、link_id=0，只能按 detail 标记清
            await s.execute(delete(ConversionRecord).where(
                ConversionRecord.action == "regression_result",
                ConversionRecord.link_id == 0,
                ConversionRecord.detail.like(f"%run_id={rid}%"),
            ))
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


async def _assemble_new_link(engine, cluster_id: int, case_id: str) -> tuple[int, str]:
    """E-17 专用：在**已有终态旧 link** 的 cluster 上组装新 link 并置 active。

    不复用 `_activate`——其取 link 用 `.one()` 且不筛 verify_status，旧失败 link 仍在场时
    会匹配多行抛 MultipleResultsFound。返回 (link_id, payload_id)。
    """
    async with AsyncSession(engine) as s:
        cluster = (await s.scalars(
            select(ErrorCluster).where(ErrorCluster.id == cluster_id))).one()
        await assemble_cluster(s, cluster)
        link = (await s.scalars(
            select(ErrorCaseLink).where(ErrorCaseLink.cluster_id == cluster_id,
                                        ErrorCaseLink.verify_status == "pending"))).one()
        link.offline_status = "active"
        link.case_id = case_id
        got = (link.id, link.payload_id)
        await s.commit()
        return got


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


# ---------- 结果行播种（第 3 刀：判定数据源 = 已落库的 verify_run_record 行） ----------
# 原假 offline（MockTransport 读面）随轮询链整删。判定信息现在全部来自行内 raw_json
# （载荷原样留档），故驱动方式 = 直接落**推送形态**的行，判据 wiring 与线上同一条路径。


def _case_row(case_id: str, *, x_pf: str, error_type=None) -> dict:
    """载荷逐 case 行（原 _case_row 的 run_id 字段属读面产物，推送载荷里没有）。"""
    row = {"case_id": case_id, "case_type": "regression_error", "pass_fail": x_pf}
    if error_type is not None:
        row["error_type"] = error_type
    return row


def _push_body(*, agent: str, version: str, run_id: str, cases: list[dict],
               cid: int | None = None, latest: str | None = None,
               prev: str | None = None, run_status: str = "completed",
               finished: str = "2026-01-05T08:00:00Z") -> dict:
    """§8.7 推送载荷（含第 3 刀新字段 prev_terminal_version，必填可 null）。"""
    return {
        "schema_version": "1.0", "agent": agent, "agent_version": version,
        "run_id": run_id, "run_status": run_status,
        "agent_latest_version": latest or version,
        "prev_terminal_version": prev, "trigger_signal_id": cid,
        "finished_ts": finished, "cases": cases,
    }


def _case_pass_of(case_id: str | None, cases: list[dict]) -> int | None:
    """run 级行 case_pass 派生（与 api.backflow._case_pass_of 同口径；na/缺行 → NULL）。"""
    if not case_id:
        return None
    row = next((c for c in cases if c.get("case_id") == case_id), None)
    if row is None or row.get("pass_fail") == "na":
        return None
    return 1 if row["pass_fail"] == "pass" else 0


async def _seed_run(engine, *, agent: str, link_id: int, case_id: str | None,
                    run_id: str, version: str, cases: list[dict],
                    latest: str | None = None, prev: str | None = None,
                    run_status: str = "completed") -> int:
    """落一条推送形态的 verify_run_record（raw_json = 载荷原样）→ 返回行 id。"""
    body = _push_body(agent=agent, version=version, run_id=run_id, cases=cases,
                      latest=latest, prev=prev, run_status=run_status)
    async with AsyncSession(engine) as s:
        row = VerifyRunRecord(
            link_id=link_id, run_id=run_id, bound_version=version,
            case_pass=_case_pass_of(case_id, cases), run_status=run_status,
            raw_json=body,
        )
        s.add(row)
        await s.flush()
        rid = row.id
        await s.commit()
        return rid


async def _push(client, body: dict):
    """HTTP 打推送端点（evaluator 静态 secret；线上唯一写入路径）。"""
    r = await client.post(f"{API}/backflow/regression-results", json=body,
                          headers=_hdr(_MOCK_SECRET))
    return r.status_code, r.json()


async def _run_judge(engine, cid: int) -> dict:
    """judge_link 单 cluster 判定（独立事务 commit；数据源 = 本 link 已落结果行）。"""
    async with AsyncSession(engine) as s2:
        cluster = (await s2.scalars(
            select(ErrorCluster).where(ErrorCluster.id == cid))).one()
        link = (await s2.scalars(
            select(ErrorCaseLink).where(ErrorCaseLink.cluster_id == cid,
                                        ErrorCaseLink.verify_status == "pending")
        )).first()
        summary = await judge_link(s2, cluster=cluster, link=link)
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
    await _seed_run(engine, agent="clm-c3", link_id=link.id, case_id="case-c3",
                    run_id="c3r1", version="3.0.0", latest="3.1.0",
                    cases=[_case_row("case-c3", x_pf="pass")])
    await _seed_run(engine, agent="clm-c3", link_id=link.id, case_id="case-c3",
                    run_id="c3r2", version="3.1.0", latest="3.1.0",
                    prev="3.0.0",  # 链上相邻：v3.0.0 本地有行 → 不触发缺行中断
                    cases=[_case_row("case-c3", x_pf="pass")])
    summary = await _run_judge(engine, cid)
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


async def c4_fail_reopen(engine, client, viewer_token) -> None:
    print("\n===== C-4 回归 fail → verify failed + cluster 回退 open =====")
    cid = await _claim_cluster(engine, client, viewer_token, agent="clm-c4",
                               snapshot='{"q": "c4"}', fv="4.0.0", case_id="case-c4", k=2)
    link = await _pending_link(engine, cid)
    await _seed_run(engine, agent="clm-c4", link_id=link.id, case_id="case-c4",
                    run_id="c4r1", version="4.0.0",
                    cases=[_case_row("case-c4", x_pf="fail",
                                     error_type="assertion_shape")])
    summary = await _run_judge(engine, cid)
    c = await _cluster(engine, cid)
    recs = await _records(engine, link.id)
    ok = (summary["outcome"] == "reopened"
          and c.status == "open"
          and "reopen" in await _conv_actions(engine, cid)
          and len(recs) == 1 and recs[0].case_pass == 0)
    check("C-4 fail → cluster open + record case_pass=0 + conv(reopen)", ok,
          f"{summary} status={c.status}")


async def c15_reclaim_new_link_e17(engine, client, viewer_token) -> None:
    print("\n===== C-15 E-17：fail 回退 open → 改 fv 再 claim → 新 link 新 payload_id =====")
    cid = await _claim_cluster(engine, client, viewer_token, agent="clm-c15",
                               snapshot='{"q": "c15"}', fv="5.0.0", case_id="case-c15", k=1)
    link1 = await _pending_link(engine, cid)
    payload1 = link1.payload_id
    await _seed_run(engine, agent="clm-c15", link_id=link1.id, case_id="case-c15",
                    run_id="c15r1", version="5.0.0",
                    cases=[_case_row("case-c15", x_pf="fail",
                                     error_type="assertion_shape")])
    s1 = await _run_judge(engine, cid)
    c = await _cluster(engine, cid)
    recs1 = await _records(engine, link1.id)
    check("C-15 第一段：回归 fail → cluster 回退 open + 旧 link failed",
          s1["outcome"] == "reopened" and c.status == "open"
          and len(recs1) == 1 and recs1[0].case_pass == 0,
          f"{s1} status={c.status} old_records={len(recs1)}")

    # 改 fix_version 再 claim（E-17 核心之一：新版本重新认领）
    status, resp = await _post(client, f"clusters/{cid}/claim", viewer_token,
                               {"fix_version": "5.1.0", "k": 1})
    c = await _cluster(engine, cid)
    check("C-15 第二段：reopen 后再 claim（fv 5.0.0→5.1.0）→ 200 + cluster 改 version",
          status == 200 and c.fix_version == "5.1.0" and c.status == "claim",
          f"http={status} fv={c.fix_version} status={c.status} resp={resp}")

    # 组装新 link（生产侧由 assemble_job 扫 open∧无现行 pending link 完成）
    link2_id, payload2 = await _assemble_new_link(engine, cid, "case-c15")
    check("C-15 第三段：再 claim 后组装出**新 link + 新 payload_id**（非复用旧 link）",
          link2_id != link1.id and payload2 != payload1,
          f"link1={link1.id}/{payload1[:8]} link2={link2_id}/{payload2[:8]}")

    # prev_terminal_version = 5.0.0（< 新 fv 5.1.0）：**故意造前序版本不在新 link 上的现场**，
    # 验缺行中断判据的「只看 ≥ fix_version 前序」边界——促成本次 claim 的那次失败不属本轮
    # K 序列，若不加该界，E-17 改版重 claim 会被永久钉死在 gap，claim 永判不出 fixed。
    await _seed_run(engine, agent="clm-c15", link_id=link2_id, case_id="case-c15",
                    run_id="c15r2", version="5.1.0", prev="5.0.0",
                    cases=[_case_row("case-c15", x_pf="pass")])
    s2 = await _run_judge(engine, cid)
    c = await _cluster(engine, cid)
    recs_old = await _records(engine, link1.id)
    recs_new = await _records(engine, link2_id)
    check("C-15 第四段：新版本回归 passed → cluster fixed + 新 link passed",
          s2["outcome"] == "fixed_auto" and c.status == "fixed"
          and len(recs_new) == 1 and recs_new[0].case_pass == 1
          and "auto_fixed" in await _conv_actions(engine, cid),
          f"{s2} status={c.status} new_records={len(recs_new)}")
    old_pf = recs_old[0].case_pass if recs_old else None
    check("C-15 第五段：旧 failed 时间线保留（不覆写、不迁移）",
          len(recs_old) == 1 and recs_old[0].case_pass == 0,
          f"old_records={len(recs_old)} case_pass={old_pf}")


async def c5_unclean_batch(engine, client, viewer_token) -> None:
    print("\n===== C-5 环境级 na run + case pass → unclean_batch（cluster 保持 claim） =====")
    cid = await _claim_cluster(engine, client, viewer_token, agent="clm-c5",
                               snapshot='{"q": "c5"}', fv="5.0.0", case_id="case-c5", k=2)
    link = await _pending_link(engine, cid)
    # 环境级 na 载体：**同 run 内另一条 case 行** pass_fail=na + error_type=circuit_open。
    # 原读面把该明细聚合成 run 级 na_error_types；推送源只有逐 case 原始行，由 online 现算
    # （verify._run_env_na）——故造数形态从 run 级字段改为「多一行 case」。
    await _seed_run(engine, agent="clm-c5", link_id=link.id, case_id="case-c5",
                    run_id="c5r1", version="5.0.0",
                    cases=[_case_row("case-c5", x_pf="pass"),
                           _case_row("case-c5-other", x_pf="na",
                                     error_type="circuit_open")])
    summary = await _run_judge(engine, cid)
    c = await _cluster(engine, cid)
    link_now = await _pending_link(engine, cid)
    async with AsyncSession(engine) as s:
        batch = (await s.scalars(
            select(NeedsReviewBatch).where(NeedsReviewBatch.run_id == "c5r1")
        )).first()
    ok = (summary["outcome"] == "unclean_batch"
          and batch is not None and batch.status == "open"
          and batch.error_type == "circuit_open"
          and c.status == "claim" and link_now is not None)  # 批引 cluster 不入 needs_review
    check("C-5 unclean：批建(uk error_type=circuit_open) + cluster 保持 claim + link 不动",
          ok, f"{summary} batch={batch.id if batch else None}")


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
    # 双簇同批的造数形态（第 3 刀）：v1 硬约束「一次回归 run 只对应一个 cluster」，故每个 link
    # 各自收一条该 run 的推送行（run_id 相同 → uk_batch_agg 同 key 聚成单批 2 ref）；
    # 环境级 na 明细由各载荷自带的 na 行现算。
    for cid, tag in zip(cids, ("a", "b")):
        lk = await _pending_link(engine, cid)
        await _seed_run(engine, agent=agent, link_id=lk.id, case_id=f"case-c6{tag}",
                        run_id="c6run", version="6.0.0",
                        cases=[_case_row(f"case-c6{tag}", x_pf="pass"),
                               _case_row(f"case-c6{tag}-other", x_pf="na",
                                         error_type="pool_error")])
    s1 = await _run_judge(engine, cids[0])
    s2 = await _run_judge(engine, cids[1])
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
    for cid2, tag in zip(cids2, ("c", "d")):
        lk = await _pending_link(engine, cid2)
        await _seed_run(engine, agent=agent, link_id=lk.id, case_id=f"case-c6e{tag}",
                        run_id="c6run2", version="6.0.0",
                        cases=[_case_row(f"case-c6e{tag}", x_pf="pass"),
                               _case_row(f"case-c6e{tag}-other", x_pf="na",
                                         error_type="pool_error")])
    for c2 in cids2:
        await _run_judge(engine, c2)
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


async def c7_na_needs_review(engine, client, viewer_token) -> None:
    print("\n===== C-7 单 case na → needs_review(na) + superseded + resolve reopen =====")
    cid = await _claim_cluster(engine, client, viewer_token, agent="clm-c7",
                               snapshot='{"q": "c7"}', fv="7.0.0", case_id="case-c7", k=2)
    link = await _pending_link(engine, cid)
    await _seed_run(engine, agent="clm-c7", link_id=link.id, case_id="case-c7",
                    run_id="c7r1", version="7.0.0",
                    cases=[_case_row("case-c7", x_pf="na", error_type="timeout")])
    summary = await _run_judge(engine, cid)
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
    print("\n===== C-9 gen>1 claim 软提示：本地零已收结果 = warning None（硬闸 P2-5） =====")
    await _seed_agent(engine, "clm-c9")
    cid = await _seed_cluster(engine, "clm-c9", '{"q": "c9"}', gen=2)
    s, b = await _post(client, f"clusters/{cid}/claim", viewer_token,
                       {"fix_version": "9.0.0", "note": "reentry 复现"})
    c = await _cluster(engine, cid)
    ok = (s == 200 and c.status == "claim" and c.claimed_by is not None
          and b.get("warning") is None)  # 该 agent 零已收结果 → 软提示退 None，claim 放行
    check("C-9 gen>1 claim 放行 + warning=None（本地零已收结果）", ok,
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
    print("\n===== C-12 欠测（本 case 未入 run）→ 读面 excluded_hit + 不自动迁移 =====")
    cid = await _claim_cluster(engine, client, viewer_token, agent="clm-c12",
                               snapshot='{"q": "c12"}', fv="12.0.0", case_id="case-c12", k=2)
    link = await _pending_link(engine, cid)
    # 欠测载体（第 3 刀）：载荷 cases[] **不含**本 link 的 case_id（原读面靠 run 级
    # excluded_case_ids；推送源只有逐 case 行，缺失即欠测）。语义与断言强度不变。
    await _seed_run(engine, agent="clm-c12", link_id=link.id, case_id="case-c12",
                    run_id="c12r1", version="12.0.0",
                    cases=[_case_row("case-c12-other", x_pf="pass")])
    summary = await _run_judge(engine, cid)
    c = await _cluster(engine, cid)
    recs = await _records(engine, link.id)
    # 读面欠测标记：原读 raw_json.excluded_hit（推送源不再写该键），现由详情端点按
    # 「载荷 cases[] 未含本 link 的 case_id」现算（api.backflow._excluded_hit）——故改打
    # 详情读面，断言强度不降（且比只查内部键更接近前端可见面）。
    s, detail = await _get(client, f"clusters/{cid}", viewer_token)
    ok = (summary["outcome"] == "pending"
          and len(recs) == 1 and recs[0].case_pass is None
          and s == 200 and detail["verify_runs"][0]["excluded_hit"] is True
          and detail["verify_runs"][0]["case_pass"] is None
          and c.status == "claim")
    check("C-12 欠测：读面 excluded_hit=True + case_pass NULL + 保持 claim", ok,
          f"{summary} records={len(recs)} status={c.status} "
          f"excluded={detail.get('verify_runs', [{}])[0].get('excluded_hit')}")


async def c13_push_judgment_orchestration(engine, client, viewer_token) -> None:
    """C-13 推送端点编排（原 recheck_job 编排的替代）：一次 HTTP 推送 → 落库 + 同事务判定
    → 终态迁移 + links_advanced 回执。

    与 C-3（judge_link 直连单簇）互补——本场景从**线上唯一写入路径**（POST
    /backflow/regression-results）进入，验 落库→判定→收敛→响应 全链 wiring；替代已删的
    worker 扫描编排（判定不再有 job，故无「扫 claim+pending」可测，改为验推送即判）。
    """
    print("\n===== C-13 推送端点编排：HTTP push → 落库+同事务判定 → fixed_auto 收口 =====")
    cid = await _claim_cluster(engine, client, viewer_token, agent="clm-c13",
                               snapshot='{"q": "c13"}', fv="13.0.0", case_id="case-c13", k=1)
    link = await _pending_link(engine, cid)
    body = _push_body(agent="clm-c13", version="13.0.0", run_id="c13r1", cid=cid,
                      cases=[_case_row("case-c13", x_pf="pass")])
    status, resp = await _push(client, body)
    c = await _cluster(engine, cid)
    recs = await _records(engine, link.id)
    ok = (status == 200 and resp["duplicated"] is False
          and resp["links_advanced"] == [link.id]  # 真发生终态迁移才列（第 3 刀语义）
          and c.status == "fixed"
          and len(recs) == 1 and recs[0].case_pass == 1
          and "auto_fixed" in await _conv_actions(engine, cid)
          and "regression_result" in await _conv_actions(engine, cid))
    check("C-13 推送编排：200 + links_advanced=[link] + cluster fixed + record×1 + 双 conv",
          ok, f"{status} {resp} status={c.status} records={len(recs)}")


async def c14_terminal_readonly_e10(engine, client, viewer_token) -> None:
    """C-14 E-10（P2-5 S-11）：终态只读显式守卫——迟到 run 不覆写不追加。

    judge_link 对**现行 pending link**收口到 passed/fixed 后，link 已非 pending；此时再对其调
    judge_link（防未来调用方误触的真实形态）→ 入口守卫（fv/case_id 校验后，verify_status!
    ="pending"）短路返 no_progress，先于落库/判定任何动作。
    迟到 run 的**生产形态**（第 3 刀）：link 已 passed ⇒ 推送端点反查不到现行 pending link
    （`_find_current_link` 只查 pending）→ 迟到行落**孤儿哨兵行**（link_id=0），既不挂到终态
    link、也进不了判定链——故同时验「复调 judge_link 被守卫挡住」与「迟到推送成孤儿留痕」。
    """
    print("\n===== C-14 E-10：judge_link 终态守卫 + 迟到 run 落孤儿不覆写 =====")
    cid = await _claim_cluster(engine, client, viewer_token, agent="clm-c14",
                               snapshot='{"q": "c14"}', fv="14.0.0", case_id="case-c14", k=1)
    link = await _pending_link(engine, cid)
    body = _push_body(agent="clm-c14", version="14.0.0", run_id="c14r1", cid=cid,
                      cases=[_case_row("case-c14", x_pf="pass")])
    status, resp = await _push(client, body)
    assert status == 200 and resp["links_advanced"] == [link.id], f"C-14 前置失败: {resp}"
    # 终态已达成：link passed（非 pending）+ cluster fixed + record×1。
    # ① 复调 judge_link（主张的误触形态）→ 守卫短路。
    summary2 = None
    async with AsyncSession(engine) as s2:
        cluster = (await s2.scalars(
            select(ErrorCluster).where(ErrorCluster.id == cid))).one()
        cur_link = (await s2.scalars(select(ErrorCaseLink)
                                     .where(ErrorCaseLink.cluster_id == cid))).one()
        summary2 = await judge_link(s2, cluster=cluster, link=cur_link)
        await s2.commit()
    # ② 迟到同版本新 run 从推送端点进来（生产唯一入口）→ 孤儿留痕，不追加到终态 link。
    late_body = _push_body(agent="clm-c14", version="14.0.0", run_id="c14r2", cid=cid,
                           cases=[_case_row("case-c14", x_pf="fail",
                                            error_type="assertion_shape")])
    late_status, late_resp = await _push(client, late_body)
    recs = await _records(engine, link.id)
    async with AsyncSession(engine) as s3:
        orphan = (await s3.scalars(
            select(VerifyRunRecord).where(VerifyRunRecord.run_id == "c14r2"))).first()
    c = await _cluster(engine, cid)
    after_pending = await _pending_link(engine, cid)
    ok = (summary2["outcome"] == "no_progress"
          and "终态只读" in (summary2.get("reason") or "")
          and len(recs) == 1  # 终态 link 时间线不追加
          and late_status == 200 and late_resp["links_advanced"] == []
          and orphan is not None and orphan.link_id == 0  # 迟到 run 落哨兵孤儿留痕
          and c.status == "fixed" and after_pending is None)
    check("C-14 E-10：守卫 no_progress + 终态 link 不追加 + 迟到 run 落孤儿 + 保持 fixed",
          ok, f"{summary2} late={late_resp.get('links_advanced')} "
              f"orphan={orphan.link_id if orphan else None} status={c.status}")


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
            await c14_terminal_readonly_e10(engine, client, viewer_token)
            await c13_push_judgment_orchestration(engine, client, viewer_token)
            await c4_fail_reopen(engine, client, viewer_token)
            await c15_reclaim_new_link_e17(engine, client, viewer_token)
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
    print("全绿：P2-4 claim 状态机 + verify 推送源判定收口 + P2-5 E-10 终态守卫"
          " + E-17 再 claim 新 link（15 场景通过）")


if __name__ == "__main__":
    asyncio.run(main())
