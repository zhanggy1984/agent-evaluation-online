"""v1.23 第 3 刀 push 结果推送接收面集成探针（detail §8.7/§8.9/§9.3）。容器内运行：

    docker exec obs-backend python /app/tests/integration/push_probe.py

前置：obs-backend 已 up（容器内 DB_HOST=mysql）。形态沿用 pull_probe：探针自建 async
engine + `create_app(Settings(app_env=test, evaluator_service_secret=…))` +
`dependency_overrides[get_session]` 挂真库 AsyncSession → httpx ASGITransport 全 HTTP 打端点
（真鉴权 header / 真错误体 / 真唯一键），DB 断言另起真 session 读。

覆盖（单测 FakeAsyncSession 装不下的实库语义：uk_verify_run 真约束 / 真 CAS 落库 /
conv 真写 / 详情端点真 SQL 组装）：
  S-1 正常推送：落 verify_run_record 一行（case_pass 由 link.case_id 命中行派生）+
      conversion_record(action='regression_result', actor_user_id=NULL) 一条；响应
      links_advanced=[link.id]、duplicated=false、cases_dropped=0；
  S-2 幂等重放：同 link+run 再推 → duplicated=true、零新增行、run_record_id 相同、
      links_advanced=[]、**cases_dropped 与首次一致**（载荷校验产物，与是否落库正交）；
  S-3 orphan（trigger_signal_id 查不到现行 link）→ link_id=哨兵 0 留档、links_advanced=[]、
      conv 仍写（cluster_id NULL、link_id 0、detail 标 orphan）；
  S-4 schema_version ≠ "1.0" → 400 ERR_PULL_0004，零落库；
  S-5 pass_fail='na' 缺 error_type → 400 ERR_PULL_0002（R-22），零落库；
  S-6 非白名单 case_type → 丢该行 + cases_dropped 计数正确，其余行正常落库（raw_json 仍原样留档）；
  S-7 claim 分支新判据正例：open cluster + fix_version='v9' + 一条 claim_ttl_expire conv +
      pending link（assembled_ts 早于该 conv 的 ts，= 回退确实发生在本轮等待之后）+ 零 run →
      详情 result_overdue.hit=true, kind='claim'，since_ts = 该 conv 的 ts；
  S-8 claim 分支**抑制反例**（防假绿对照，必须有）：同 S-7，但 cluster 处于未到期 claim
      （status='claim' ∧ claim_due_ts 在未来）→ hit=false；再把 claim_due_ts 拨到过去
      （回退前一刻）→ hit=true —— 证 S-8 的 false 是抑制生效，不是链路整体不工作；
  S-9 assembled 分支正例：pending link 仍 assembled 且 now - assembled_ts ≥ N 天
      （N = dict_config claim_ttl_days，默认 14）→ hit=true, kind='assembled'。
  S-10/S-11 **回归护栏（claim 分支条件 ③ 的 pending 谓词）**：完整复刻 S-7 现场，只把
      「cluster 离开等结果态」这一维换成真实落库形态 —— S-10 = fixed_review(approve=True)
      之后（cluster.status='fixed' ∧ link verify_status='passed'，claim.py:246）、
      S-11 = ignore 之后（status='inactive' ∧ link 'superseded'）→ 均须 hit=false。
      **有效性已实测**：临时把条件 ③ 的 `anchor.verify_status == "pending"` 去掉（退回
      `links[0]` 兜底）后 S-10/S-11 双双转红、S-7 仍绿，改回即全绿——即这两条断言真的
      钉住了那个谓词，不是「看起来像护栏」。（场景造数把 link.assembled_ts 拨到 20 天前、
      早于回退 conv 的 ts，使条件 ⑤ 成立，否则 ⑤ 会替 ③ 挡下命中、护栏失效。）
  S-12 **回归护栏（claim 分支条件 ⑤ 的本轮性）**：复刻实测出的 reopen/requeue 现场 ——
      cluster 已回退 open 并被重新组装（全新 pending link、assembled_ts=now、零 run），
      fix_version 与 30 天前的 claim_ttl_expire conv 都还留着 → ①②③④ 全成立，须 hit=false。
      **有效性已实测**：临时去掉条件 ⑤ 后 S-12 转红（命中且 since_ts = 30 天前）、其余仍绿，
      改回即全绿。
  S-13 载荷内 case_id 重复 → 400 ERR_PULL_0002（消息含重复值 + 首次下标）+ run/conv 零落库；
      反证：case_id 互不相同的多行（含非白名单 case_type 丢行）→ 200 正常落库。

隔离：cluster.agent 前缀 push-%（≤64 字符），开头/结尾幂等清理（外键序 conv→link→cluster
+ 哨兵行按探针 run_id/detail 标记识别，不按 link_id=0 一刀切）+ 探针 viewer 用户。
退出码全绿 0。
"""
import asyncio
import hashlib
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app")

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import delete, select, update  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.api.backflow import ORPHAN_LINK_ID, OVERDUE_CAPTION  # noqa: E402
from app.backflow.claim import CLAIM_TTL_DAYS_KEY, CLAIM_TTL_DEFAULT_DAYS  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.core.db import get_session  # noqa: E402
from app.core.dict_config import get_global_int  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.error_flow import (  # noqa: E402
    ConversionRecord,
    ErrorCaseLink,
    ErrorCluster,
    VerifyRunRecord,
)
from app.models.user import User  # noqa: E402

FAILURES: list[str] = []
CHECKS: list[str] = []
IFACE = "POST /api/probe/{id}"
NOW = datetime.now(timezone.utc).replace(tzinfo=None)
_SECRET = "probe-push-secret"
_JWT = "probe-jwt-0123456789abcdefghijklmnopqrstuvwxyz"
VIEWER = "push-probe-viewer"
API = "/api/v1"
PUSH_URL = f"{API}/backflow/regression-results"
AGENT = "push-agent"
RUN_ID_PREFIX = "push-run-"  # 探针专属 run_id 前缀（哨兵行/清理按它识别）
GHOST_CLUSTER_ID = 999999999  # 无 cluster 无 link 的 trigger_signal_id（orphan 现场）
_settings_cache: dict = {}


def check(name: str, ok: bool, detail: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    CHECKS.append(name)
    if not ok:
        FAILURES.append(name)


def _app_settings() -> Settings:
    if "s" not in _settings_cache:
        _settings_cache["s"] = Settings(app_env="test", resource_env="dev",
                                        jwt_secret=_JWT, evaluator_service_secret=_SECRET)
    return _settings_cache["s"]


def _hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _body(**over) -> dict:
    """§8.7 载荷默认值（agent/agent_version/run_id 已被场景覆盖）。"""
    body = dict(
        schema_version="1.0", agent=AGENT, agent_version="1.5.0",
        run_id=f"{RUN_ID_PREFIX}0", run_status="completed",
        bound_version_first_seen=True, agent_latest_version="1.5.0",
        finished_ts="2026-01-05T08:00:00Z",
        cases=[{"case_id": "c-1", "case_type": "regression_error", "pass_fail": "pass"}],
    )
    body.update(over)
    return body


async def _push(client, **over):
    r = await client.post(PUSH_URL, json=_body(**over),
                          headers=_hdr(_SECRET))
    return r.status_code, r.json()


async def _detail(client, cluster_id: int, token: str):
    r = await client.get(f"{API}/backflow/clusters/{cluster_id}", headers=_hdr(token))
    return r.status_code, r.json()


# ---------- DB 基建 ----------


async def _cleanup(engine) -> None:
    """清 push-% 残留（外键序：conv → link → cluster）+ 哨兵行 + 探针 viewer。

    哨兵行（link_id=0）无 cluster 归属、cluster_id 亦为 NULL，按 cluster 前缀清不到——
    用探针专属 run_id 前缀 + conv detail 里的 `run_id=push-` 标记识别，**不按 link_id=0
    一刀切**（该哨兵位可能承载非探针的历史 orphan 数据，不能误删）。
    """
    async with AsyncSession(engine) as s:
        sub = select(ErrorCluster.id).where(ErrorCluster.agent.like("push-%"))
        await s.execute(delete(ConversionRecord).where(ConversionRecord.cluster_id.in_(sub)))
        await s.execute(delete(ConversionRecord).where(
            ConversionRecord.action == "regression_result",
            ConversionRecord.link_id == ORPHAN_LINK_ID,
            ConversionRecord.detail.like(f"%run_id={RUN_ID_PREFIX}%"),
        ))
        await s.execute(delete(ErrorCaseLink).where(ErrorCaseLink.cluster_id.in_(sub)))
        await s.execute(delete(VerifyRunRecord).where(
            VerifyRunRecord.run_id.like(f"{RUN_ID_PREFIX}%")))
        await s.execute(delete(ErrorCluster).where(ErrorCluster.agent.like("push-%")))
        await s.execute(delete(User).where(User.username == VIEWER))
        await s.commit()


async def _ensure_user(engine, name: str, role: str) -> int:
    async with AsyncSession(engine) as s:
        u = User(username=name, password_hash="x" * 60, role=role, status=1)
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
        return uid


async def _seed_cluster(engine, agent: str, *, status="open", fix_version=None,
                        claimed_at=None, claim_due_ts=None) -> int:
    """落 cluster（input_hash 由 agent 名派生：一场景一簇，不撞 uk_cluster_dedup）。"""
    async with AsyncSession(engine) as s:
        row = ErrorCluster(
            agent=agent, interface=IFACE, layer="L1", error_type="llm_timeout",
            input_hash=hashlib.sha256(agent.encode()).hexdigest(),
            input_snapshot='{"question": "probe"}', input_truncated=0,
            error_msg="provider timeout", first_trace_id=f"{agent}-1",
            trigger_version="2026.09.09-r1", fix_version=fix_version,
            first_ts=NOW, latest_ts=NOW, count=1, generation=1, status=status,
            claimed_at=claimed_at, claim_due_ts=claim_due_ts,
        )
        s.add(row)
        await s.flush()
        cid = row.id
        await s.commit()
        return cid


async def _seed_link(engine, cluster_id: int, *, offline_status="active",
                     assembled_ts=None, case_id="c-1",
                     verify_status="pending") -> int:
    """落 link（缺省现行 pending：cur_key 生成列占位；同 cluster 同 case_type 至多一条）。

    verify_status 非 pending 时 cur_key 生成列自动为 NULL（终态释放占位，可多条并存），
    S-10/S-11 用它复刻「cluster 离开等结果态 → link 已被终结」的落库形态。
    """
    async with AsyncSession(engine) as s:
        row = ErrorCaseLink(
            cluster_id=cluster_id, payload_id=str(uuid.uuid4()), case_id=case_id,
            case_type="regression_error",
            source_trace_id=f"push-trace-{uuid.uuid4().hex[:8]}",
            trigger_version="2026.09.09-r1", fix_version=None, input_truncated=0,
            offline_status=offline_status, verify_status=verify_status, payload_json="{}",
            assembled_ts=assembled_ts if assembled_ts is not None else NOW,
        )
        s.add(row)
        await s.flush()
        lid = row.id
        await s.commit()
        return lid


async def _seed_conv(engine, cluster_id: int, action: str, *, ts=None, detail=None) -> None:
    """落 conv（ts 拨到指定时刻：探针不等真实时钟）。"""
    async with AsyncSession(engine) as s:
        row = ConversionRecord(cluster_id=cluster_id, action=action, link_id=None,
                               detail=detail or f"probe {action}", actor_user_id=None)
        if ts is not None:
            row.ts = ts
        s.add(row)
        await s.commit()


async def _runs_of(engine, link_id: int) -> list:
    async with AsyncSession(engine) as s:
        return list((await s.scalars(
            select(VerifyRunRecord).where(VerifyRunRecord.link_id == link_id))).all())


async def _convs_of(engine, cluster_id: int) -> list:
    async with AsyncSession(engine) as s:
        return list((await s.scalars(
            select(ConversionRecord).where(ConversionRecord.cluster_id == cluster_id))).all())


async def _set_due(engine, cluster_id: int, due: datetime) -> None:
    async with AsyncSession(engine) as s:
        await s.execute(update(ErrorCluster).where(ErrorCluster.id == cluster_id)
                        .values(claim_due_ts=due))
        await s.commit()


def _ms_aligned(dt: datetime) -> datetime:
    """对齐到 DT3（DATETIME(3)）精度：跨库往返后 isoformat 才与本侧逐字可比。"""
    return dt.replace(microsecond=0)


# ---------- S 场景 ----------


async def s1_normal_push(engine, client) -> None:
    print("\n===== S-1 正常推送：run 行 + conv(regression_result) =====")
    cid = await _seed_cluster(engine, "push-s1")
    lid = await _seed_link(engine, cid)
    status, body = await _push(client, trigger_signal_id=cid, run_id=f"{RUN_ID_PREFIX}1")
    runs = await _runs_of(engine, lid)
    convs = await _convs_of(engine, cid)
    rec = runs[0] if runs else None
    conv = convs[0] if convs else None
    check("S-1 200 + links_advanced=[link] + run/conv 各一行（case_pass=1、系统动作）",
          status == 200 and body["accepted"] is True and body["duplicated"] is False
          and body["links_advanced"] == [lid] and body["cases_dropped"] == 0
          and rec is not None and rec.id == body["run_record_id"]
          and rec.case_pass == 1 and rec.bound_version == "1.5.0"
          and rec.run_status == "completed"
          and (rec.raw_json or {}).get("finished_ts") == "2026-01-05T08:00:00Z"
          and conv is not None and conv.action == "regression_result"
          and conv.cluster_id == cid and conv.link_id == lid
          and conv.actor_user_id is None,
          f"{status} {body} runs={len(runs)} convs={[(c.action, c.link_id) for c in convs]}")


async def s2_idempotent_replay(engine, client) -> None:
    print("\n===== S-2 幂等重放：duplicated + 零新增 + cases_dropped 一致 =====")
    cid = await _seed_cluster(engine, "push-s2")
    lid = await _seed_link(engine, cid)
    cases = [
        {"case_id": "c-1", "case_type": "regression_error", "pass_fail": "pass"},
        {"case_id": "c-2", "case_type": "random_access", "pass_fail": "fail"},
    ]
    s1, b1 = await _push(client, trigger_signal_id=cid, run_id=f"{RUN_ID_PREFIX}2", cases=cases)
    s2, b2 = await _push(client, trigger_signal_id=cid, run_id=f"{RUN_ID_PREFIX}2", cases=cases)
    runs = await _runs_of(engine, lid)
    convs = await _convs_of(engine, cid)
    check("S-2 首推 duplicated=false / 重放 duplicated=true + 同 run_record_id"
          " + 零新增行 + cases_dropped 与首次一致",
          s1 == 200 and s2 == 200 and b1["duplicated"] is False and b2["duplicated"] is True
          and b1["cases_dropped"] == b2["cases_dropped"] == 1
          and b1["run_record_id"] == b2["run_record_id"]
          and b2["links_advanced"] == []
          and len(runs) == 1 and len(convs) == 1,
          f"first={s1} {b1} replay={s2} {b2} runs={len(runs)} convs={len(convs)}")


async def s3_orphan(engine, client) -> None:
    print("\n===== S-3 orphan：无现行 link → 哨兵 0 留档 + 不推进 =====")
    status, body = await _push(client, trigger_signal_id=GHOST_CLUSTER_ID,
                               run_id=f"{RUN_ID_PREFIX}3")
    runs = await _runs_of(engine, ORPHAN_LINK_ID)
    orphan_conv = await _orphan_conv(engine, f"{RUN_ID_PREFIX}3")
    rec = next((r for r in runs if r.run_id == f"{RUN_ID_PREFIX}3"), None)
    check("S-3 200 + links_advanced=[] + link_id=0 哨兵行 + conv(cluster_id NULL) 照写标 orphan",
          status == 200 and body["links_advanced"] == [] and body["duplicated"] is False
          and rec is not None and rec.id == body["run_record_id"] and rec.case_pass is None
          and orphan_conv is not None
          and orphan_conv.cluster_id is None and orphan_conv.link_id == ORPHAN_LINK_ID
          and "orphan" in (orphan_conv.detail or ""),
          f"{status} {body} sentinel_runs={len(runs)} conv={orphan_conv and orphan_conv.detail!r}")


async def _orphan_conv(engine, run_id: str):
    async with AsyncSession(engine) as s:
        return await s.scalar(
            select(ConversionRecord).where(
                ConversionRecord.action == "regression_result",
                ConversionRecord.link_id == ORPHAN_LINK_ID,
                ConversionRecord.detail.like(f"%run_id={run_id} %"),
            ).limit(1)
        )


async def s4_schema_version_rejected(engine, client) -> None:
    print("\n===== S-4 schema_version ≠ 1.0 → 400 ERR_PULL_0004 零落库 =====")
    cid = await _seed_cluster(engine, "push-s4")
    lid = await _seed_link(engine, cid)
    status, body = await _push(client, trigger_signal_id=cid, run_id=f"{RUN_ID_PREFIX}4",
                               schema_version="2.0")
    check("S-4 400 ERR_PULL_0004 + verify_run_record/conversion_record 零落",
          status == 400 and body.get("code") == "ERR_PULL_0004"
          and not await _runs_of(engine, lid) and not await _convs_of(engine, cid),
          f"{status} {body}")


async def s5_na_without_error_type(engine, client) -> None:
    print("\n===== S-5 pass_fail='na' 缺 error_type → 400 ERR_PULL_0002 零落库 =====")
    cid = await _seed_cluster(engine, "push-s5")
    lid = await _seed_link(engine, cid)
    cases = [{"case_id": "c-1", "case_type": "regression_error", "pass_fail": "na"}]
    status, body = await _push(client, trigger_signal_id=cid, run_id=f"{RUN_ID_PREFIX}5",
                               cases=cases)
    check("S-5 400 ERR_PULL_0002（R-22 不变量）+ 零落库",
          status == 400 and body.get("code") == "ERR_PULL_0002"
          and not await _runs_of(engine, lid) and not await _convs_of(engine, cid),
          f"{status} {body}")


async def s6_non_whitelist_case_type(engine, client) -> None:
    print("\n===== S-6 非白名单 case_type：丢该行计数，其余正常落库 =====")
    cid = await _seed_cluster(engine, "push-s6")
    lid = await _seed_link(engine, cid)
    cases = [
        {"case_id": "c-1", "case_type": "regression_error", "pass_fail": "pass"},
        {"case_id": "c-2", "case_type": "random_access", "pass_fail": "fail"},
        {"case_id": "c-9", "case_type": "regression_error", "pass_fail": "fail"},
    ]
    status, body = await _push(client, trigger_signal_id=cid, run_id=f"{RUN_ID_PREFIX}6",
                               cases=cases)
    runs = await _runs_of(engine, lid)
    rec = runs[0] if runs else None
    raw_cases = (rec.raw_json or {}).get("cases", []) if rec is not None else []
    check("S-6 cases_dropped=1 + 其余行正常落库（case_pass 取命中行 c-1=pass）+ raw 原样留档",
          status == 200 and body["cases_dropped"] == 1 and body["links_advanced"] == [lid]
          and len(runs) == 1 and rec.case_pass == 1
          and [c["case_type"] for c in raw_cases]
          == ["regression_error", "random_access", "regression_error"],
          f"{status} {body} runs={len(runs)} raw_cases={len(raw_cases)}")


async def s7_claim_overdue_hit(engine, client, token) -> None:
    print("\n===== S-7 claim 分支正例：TTL 回退现场（claim_ttl_expire conv） =====")
    cid = await _seed_cluster(engine, "push-s7", status="open", fix_version="v9")
    # 本轮等待起点（= link 组装时刻）必须**早于**回退 conv 的 ts：真实链是
    # 组装(assembled_ts) → offline 认领(claim) → 14 天 TTL 超窗 → claim_ttl_job 回退并写
    # conv(action='claim_ttl_expire')，回退只能发生在本轮开始之后。这不是迁就实现的造数，
    # 而是条件 ⑤（`latest_expire.ts > anchor.assembled_ts`）描述的真实现场：
    # 早于本轮起点的回退记录 = 上一轮的陈旧证据，不能拿来判本轮停摆（对照见 S-12）。
    await _seed_link(engine, cid, offline_status="active",
                     assembled_ts=_ms_aligned(NOW - timedelta(days=20)))
    expire_ts = _ms_aligned(NOW - timedelta(days=1))
    await _seed_conv(engine, cid, "claim_ttl_expire", ts=expire_ts,
                     detail="claim TTL 超窗 → open；fix_version=v9 保留溯源")
    status, d = await _detail(client, cid, token)
    od = d.get("result_overdue") or {}
    check("S-7 hit=true kind=claim + since_ts=回退 conv 的 ts（claimed_at 已被回退清空）",
          status == 200 and od.get("hit") is True and od.get("kind") == "claim"
          and od.get("since_ts") == expire_ts.isoformat()
          and od.get("caption") == OVERDUE_CAPTION,
          f"{status} overdue={od}")


async def s8_claim_suppressed(engine, client, token) -> None:
    print("\n===== S-8 claim 分支抑制反例（防假绿对照） =====")
    cid = await _seed_cluster(engine, "push-s8", status="claim", fix_version="v9",
                              claimed_at=NOW, claim_due_ts=NOW + timedelta(days=13))
    # 同 S-7：组装（本轮起点）早于上一轮回退 conv，再被人工重新 claim（claimed_at=NOW）
    await _seed_link(engine, cid, offline_status="active",
                     assembled_ts=_ms_aligned(NOW - timedelta(days=20)))
    expire_ts = _ms_aligned(NOW - timedelta(days=2))
    await _seed_conv(engine, cid, "claim_ttl_expire", ts=expire_ts,
                     detail="claim TTL 超窗 → open")
    status, d = await _detail(client, cid, token)
    od = d.get("result_overdue") or {}
    check("S-8 有效 claim 期内（due 在未来）→ hit=false（旧回退 conv 不误报停摆）",
          status == 200 and od.get("hit") is False and od.get("kind") is None,
          f"{status} overdue={od}")
    # 对照组：同一现场把 due 拨到过去（= 回退前一刻）→ 必须命中，证 S-8 的 false 由抑制给出
    await _set_due(engine, cid, NOW - timedelta(seconds=1))
    status2, d2 = await _detail(client, cid, token)
    od2 = d2.get("result_overdue") or {}
    check("S-8 对照组 same 现场 due 已过 → hit=true kind=claim（证抑制条件真的在起作用）",
          status2 == 200 and od2.get("hit") is True and od2.get("kind") == "claim"
          and od2.get("since_ts") == expire_ts.isoformat(),
          f"{status2} overdue={od2}")


async def s10_fixed_no_false_positive(engine, client, token) -> None:
    print("\n===== S-10 fixed 误报对照：cluster 已 fixed + link 非 pending → 不得报停摆 =====")
    # 完整复刻 S-7 的现场（fix_version 非空 + claim_ttl_expire conv + 有 link + 零 run），
    # 只把「cluster 离开等结果态」这一维换成真实落库形态：fixed_review(approve=True) →
    # cluster.status='fixed' ∧ 现行 link verify_status='passed'（claim.py:246）。
    # 少了条件 ③ 的 pending 谓词时，anchor 走 links[0] 兜底 → 四条件全成立 → 假命中。
    cid = await _seed_cluster(engine, "push-s10", status="fixed", fix_version="v9")
    # assembled_ts 同样取在场（且早于回退 conv），使条件 ⑤ 成立——否则 ⑤ 会替 ③ 挡住命中，
    # 这条护栏就测不到 ③ 的 pending 谓词了（对照有效性要求两个谓词各自可被单独证伪）。
    await _seed_link(engine, cid, offline_status="active", verify_status="passed",
                     assembled_ts=_ms_aligned(NOW - timedelta(days=20)))
    await _seed_conv(engine, cid, "claim_ttl_expire",
                     ts=_ms_aligned(NOW - timedelta(days=1)),
                     detail="claim TTL 超窗 → open；fix_version=v9 保留溯源")
    status, d = await _detail(client, cid, token)
    od = d.get("result_overdue") or {}
    shown = [(lk["link_id"], lk["verify_status"]) for lk in d.get("links", [])]
    check("S-10 fixed 簇（link=passed）→ hit=false（回归护栏：去 pending 谓词必转红）",
          status == 200 and od.get("hit") is False and od.get("kind") is None,
          f"{status} links={shown} overdue={od}")


async def s11_inactive_no_false_positive(engine, client, token) -> None:
    print("\n===== S-11 inactive 误报对照：cluster inactive + link superseded =====")
    # 同 S-10 同构：ignore → cluster.status='inactive' ∧ 现行 pending link superseded
    # （claim.py ignore_cluster / backflow.py ignore 端点）。
    cid = await _seed_cluster(engine, "push-s11", status="inactive", fix_version="v9")
    await _seed_link(engine, cid, offline_status="active", verify_status="superseded",
                     assembled_ts=_ms_aligned(NOW - timedelta(days=20)))
    await _seed_conv(engine, cid, "claim_ttl_expire",
                     ts=_ms_aligned(NOW - timedelta(days=1)),
                     detail="claim TTL 超窗 → open；fix_version=v9 保留溯源")
    status, d = await _detail(client, cid, token)
    od = d.get("result_overdue") or {}
    shown = [(lk["link_id"], lk["verify_status"]) for lk in d.get("links", [])]
    check("S-11 inactive 簇（link=superseded）→ hit=false（回归护栏：去 pending 谓词必转红）",
          status == 200 and od.get("hit") is False and od.get("kind") is None,
          f"{status} links={shown} overdue={od}")


async def s9_assembled_overdue(engine, client, token) -> None:
    print("\n===== S-9 assembled 分支正例：超 N 天未拉取 =====")
    async with AsyncSession(engine) as s:
        n_days = await get_global_int(s, CLAIM_TTL_DAYS_KEY, CLAIM_TTL_DEFAULT_DAYS)
    assembled_ts = _ms_aligned(NOW - timedelta(days=n_days + 1))
    cid = await _seed_cluster(engine, "push-s9")
    await _seed_link(engine, cid, offline_status="assembled", assembled_ts=assembled_ts)
    status, d = await _detail(client, cid, token)
    od = d.get("result_overdue") or {}
    check("S-9 hit=true kind=assembled + since_ts=assembled_ts（N=claim_ttl_days 同源）",
          status == 200 and od.get("hit") is True and od.get("kind") == "assembled"
          and od.get("since_ts") == assembled_ts.isoformat()
          and od.get("caption") == OVERDUE_CAPTION,
          f"{status} N={n_days} overdue={od}")


async def s12_reopen_stale_expire_no_false_positive(engine, client, token) -> None:
    print("\n===== S-12 reopen 误报对照：陈旧回退 conv + 本轮全新组装的 pending link =====")
    # 复刻实测出的 reopen/requeue 现场：cluster 回退 open 后被重新组装（assemble_job 给无
    # pending link 的 open 簇装配一条**全新** pending link，uk_link_current 不拦），而
    # fix_version 与 30 天前那条 claim_ttl_expire conv 都还留着（`reopen_cluster` 只置
    # status='open'，不清 fix_version/conv）→ ①②③④ **全成立**，新 link 零 run。
    # 条件 ③ 的 pending 谓词在这里挡不住（link 确实是 pending，只是换了新的），必须靠 ⑤
    # 用本轮起点（assembled_ts=刚组装）比掉那条陈旧回退记录。
    cid = await _seed_cluster(engine, "push-s12", status="open", fix_version="v9")
    await _seed_link(engine, cid, offline_status="active",
                     assembled_ts=_ms_aligned(NOW))  # 本轮起点 = 刚刚组装
    await _seed_conv(engine, cid, "claim_ttl_expire",
                     ts=_ms_aligned(NOW - timedelta(days=30)),
                     detail="上一轮 claim TTL 超窗 → open；本轮已重新组装")
    status, d = await _detail(client, cid, token)
    od = d.get("result_overdue") or {}
    check("S-12 陈旧回退 + 本轮新 link → hit=false（回归护栏：去条件 ⑤ 必转红）",
          status == 200 and od.get("hit") is False and od.get("kind") is None,
          f"{status} overdue={od}")


async def s13_duplicate_case_id_rejected(engine, client) -> None:
    print("\n===== S-13 载荷内 case_id 重复 → 400 ERR_PULL_0002 整单拒 + 零落库 =====")
    cid = await _seed_cluster(engine, "push-s13")
    lid = await _seed_link(engine, cid)
    # 同一 case 一 pass 一 fail：静默取首条会按 pass 收敛（且落库后不可回改），必须整单拒
    dup_cases = [
        {"case_id": "c-dup", "case_type": "regression_error", "pass_fail": "pass"},
        {"case_id": "c-dup", "case_type": "regression_error", "pass_fail": "fail",
         "error_type": "llm_timeout"},
    ]
    status, body = await _push(client, trigger_signal_id=cid, run_id=f"{RUN_ID_PREFIX}dupe",
                               cases=dup_cases)
    msg = body.get("message") or ""
    runs = await _runs_of(engine, lid)
    convs = await _convs_of(engine, cid)
    check("S-13 400 ERR_PULL_0002（消息含重复值 + 首次下标 cases[0]）+ run/conv 零落",
          status == 400 and body.get("code") == "ERR_PULL_0002"
          and "c-dup" in msg and "cases[0]" in msg
          and not runs and not convs,
          f"{status} {body} runs={len(runs)} convs={len(convs)}")
    # 反证：多行且 case_id 互不相同（含一行非白名单 case_type 走「丢行」）→ 200 正常落库，
    # 证去重只打「同一 case 两条」，不误伤行级多行与非白名单丢行策略
    ok_cases = [
        {"case_id": "c-a", "case_type": "regression_error", "pass_fail": "pass"},
        {"case_id": "c-b", "case_type": "regression_error", "pass_fail": "na",
         "error_type": "scheduler_unexecuted"},
        {"case_id": "c-c", "case_type": "not_whitelisted", "pass_fail": "fail"},
    ]
    status2, body2 = await _push(client, trigger_signal_id=cid, run_id=f"{RUN_ID_PREFIX}ok",
                                 cases=ok_cases)
    runs2 = await _runs_of(engine, lid)
    check("S-13 反证 非重复多行（含非白名单丢行）→ 200 cases_dropped=1 且落 1 行",
          status2 == 200 and body2.get("cases_dropped") == 1 and len(runs2) == 1,
          f"{status2} {body2} runs={len(runs2)}")


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
        await _cleanup(engine)  # 幂等：清 push-% 残留（防重跑累积干扰断言）
        viewer_id = await _ensure_user(engine, VIEWER, "viewer")
        token = create_access_token(_app_settings(), viewer_id, "viewer")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://probe") as client:
            await s1_normal_push(engine, client)
            await s2_idempotent_replay(engine, client)
            await s3_orphan(engine, client)
            await s4_schema_version_rejected(engine, client)
            await s5_na_without_error_type(engine, client)
            await s6_non_whitelist_case_type(engine, client)
            await s7_claim_overdue_hit(engine, client, token)
            await s8_claim_suppressed(engine, client, token)
            await s9_assembled_overdue(engine, client, token)
            await s10_fixed_no_false_positive(engine, client, token)
            await s11_inactive_no_false_positive(engine, client, token)
            await s12_reopen_stale_expire_no_false_positive(engine, client, token)
            await s13_duplicate_case_id_rejected(engine, client)
    finally:
        await _cleanup(engine)
        await engine.dispose()
    print("\n===== push_probe 结果 =====")
    if FAILURES:
        print(f"FAIL: {len(FAILURES)}/{len(CHECKS)} 项失败 → {FAILURES}")
        sys.exit(1)
    print(f"全绿：push 结果推送接收面接收/幂等/orphan/校验/丢行/overdue 判据 "
          f"{len(CHECKS)}/{len(CHECKS)} 场景通过")


if __name__ == "__main__":
    asyncio.run(main())
