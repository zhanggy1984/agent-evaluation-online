"""v1.23 第 2/3 刀 push 结果推送接收面集成探针（detail §8.7/§8.9/§9.3）。容器内运行：

    docker exec obs-backend python /app/tests/integration/push_probe.py

前置：obs-backend 已 up（容器内 DB_HOST=mysql）。形态沿用 pull_probe：探针自建 async
engine + `create_app(Settings(app_env=test, evaluator_service_secret=…))` +
`dependency_overrides[get_session]` 挂真库 AsyncSession → httpx ASGITransport 全 HTTP 打端点
（真鉴权 header / 真错误体 / 真唯一键），DB 断言另起真 session 读。

覆盖（单测 FakeAsyncSession 装不下的实库语义：uk_verify_run 真约束 / 真 CAS 落库 /
conv 真写 / 详情端点真 SQL 组装 / **落库即判同事务**）：
  S-1 正常推送（第 3 刀扩为判定写回正例）：claim 簇 + pending link + k=1，推一条 pass →
      落 verify_run_record 一行（case_pass 由 link.case_id 命中行派生）+
      conversion_record(action='regression_result', actor_user_id=NULL) 一条；**判定同事务
      写回**：link.verify_status='passed'、cluster.status='fixed'、auto_fixed conv 落库；
      响应 links_advanced=[link.id]（= 真发生终态迁移）、duplicated=false、cases_dropped=0；
  S-2 幂等重放：同 link+run 再推 → duplicated=true、零新增行、run_record_id 相同、
      links_advanced=[]、**cases_dropped 与首次一致**（载荷校验产物，与是否落库正交）；
  S-3 orphan（trigger_signal_id 查不到现行 link）→ link_id=哨兵 0 留档、links_advanced=[]、
      conv 仍写（cluster_id NULL、link_id 0、detail 标 orphan）；
  S-4 schema_version ≠ "1.0" → 400 ERR_PULL_0004，零落库；
  S-5 pass_fail='na' 缺 error_type → 400 ERR_PULL_0002（R-22），零落库；
  S-6 非白名单 case_type → 丢该行 + cases_dropped 计数正确，其余行正常落库（raw_json 仍原样留档）；
      claim 簇 k=2 下同时断言判定跑过但未达终态（links_advanced=[]）；
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
  S-14 **缺行中断判据（第 3 刀新增，(a) 正例）**：v1.0.0 pass（prev=null）→ 中间版本 v2.0.0
      的推送全丢（在线无该行）→ v3.0.0 pass 且 prev_terminal_version='2.0.0' 本地查无 →
      判 gap：cluster 保持 claim、link 仍 pending、K **不累计**。k 刻意取 2：移除该判据后
      v1+v3 两条相邻纯净 pass 即达 K 满 → 本断言转红。
      **有效性已实测**：临时注释掉 verify.judge_link 的缺行中断分支后 S-14 转红（cluster
      变 fixed、links_advanced=[link]）、S-15 与其余场景仍绿，改回即全绿——即该断言真的钉住
      了那条判据，不是「看起来像护栏」。
  S-15 **反假绿对照（(b)）**：同形态但中间版本本地**有**行（三版链式 pass、prev 逐版命中）
      → 正常累计至 k=3 → 前两推 pending、末推 fixed_auto + link passed。与 S-14 只差
      「中间版本行在不在」一个条件而结论相反，证明 S-14 的「保持 claim」是判据生效而非链路
      失效。（S-14/S-15 用小 k 是刻意的：k 越大越到不了 K 满，断言就转不了红。）
  S-16 **本批 (a) 顺序一（判定安全网核心现场）**：推送先到、cluster 仍 open（建簇→自动组装
      →offline 拉走→推回时还没认领）→ 判定被 `cluster.status=='claim'` 守卫跳过（响应
      links_advanced=[]，行照落）→ 走真实 claim 端点认领 → **run_rejudge 跑一轮** → link
      passed / cluster fixed。无 rejudge 则此 link 永久 pending（认领不是事件，不会再触发判定）。
  S-17 **(a) 顺序二（S-16 的对照）**：只差「推送时簇已 claim」一维 → 推送端点内**立即**判掉
      （links_advanced=[link]，不等任何 job）。两场景结论相反 ⇒ S-16 的「要等 job」是守卫语义
      使然，不是判定链路整体不工作。**有效性已实测**：临时注释掉 rejudge 调用后 S-16 转红
      （link 仍 pending）、S-17 仍绿，改回即全绿。
  S-18 **(b) 判定中途抛异常 → 降级**：桩掉判定内核，使其**先写一半**（text UPDATE 把 link 改
      superseded）**再抛真 DB 错误**（查不存在的表）→ 半笔被 savepoint 回退（link 仍 pending）、
      推送仍 200、run 行已落库；恢复内核后 rejudge 补判收敛。**为什么桩必须「先写一半再抛」**：
      第一版只断言「抛错后仍 200 + 行落库」，去掉 savepoint 后**依然全绿** —— MySQL 的语句级
      报错不作废整个事务，裸调用时 commit 照样成功，那条断言等于没钉住任何东西（假绿）。
      **有效性已实测**：把 `async with session.begin_nested()` 换成裸调用后 S-18 转红
      （半笔 link=superseded 落库 + rejudge 再找不到 pending link），其余场景仍绿，改回即全绿。
  S-19 **(c) 缺行中断判据改 agent 级**：同 agent 三簇并行 —— B 的 prev=v1.0.0 其行落在**同
      agent 的 A 簇**上（link 级查 → 假 gap → B 永远推不进，k=1 本应一次收敛）→ 按 agent 级查
      → 无 gap → B 正常累计 fixed；C 的 prev=9.9.9 全库无该版本行 → **仍判 gap**（防假连续
      未削弱）。顺带断言 (g) 读面派生标记 result_gap_suspected = A:false / C:true。
      **有效性已实测**：把判据改回 link 级（只查本 link 行集）后 S-19 转红（B 卡 pending）、
      其余仍绿，改回即全绿。
  S-20 **(d) 老格式行（raw_json 无 `cases` 键，第 2 刀期 writer）→ 不可判**：直接造一条老格式
      v1.5.0 行在前，再推逐 case 的 v2.0.0 pass → 保持 pending（若当 missing 跨过，k=1 下
      v2 的纯净 pass 直接算满 K → **假 fixed**）。

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
from sqlalchemy import delete, select, text, update  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

import app.api.backflow as backflow_api  # noqa: E402  （(b) 场景按模块属性打桩判定内核）
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
from app.worker.rejudge_job import run_rejudge  # noqa: E402  （本批安全网：探针直接跑一轮）

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
    """§8.7 载荷默认值（agent/agent_version/run_id 已被场景覆盖）。

    prev_terminal_version 是第 3 刀新字段：**必填但值可 null**（null = 该 agent 此前无终态 run）。
    `bound_version_first_seen` 已随本批 (e) 从载荷删除（必填却零读取点）。
    """
    body = dict(
        schema_version="1.0", agent=AGENT, agent_version="1.5.0",
        run_id=f"{RUN_ID_PREFIX}0", run_status="completed",
        agent_latest_version="1.5.0",
        prev_terminal_version=None,
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
                        claimed_at=None, claim_due_ts=None, claim_k=2,
                        input_hash=None) -> int:
    """落 cluster（input_hash 由 agent 名派生：一场景一簇，不撞 uk_cluster_dedup）。

    claim_k：判定收敛阈值（第 3 刀场景按需取 1/2/3——k 越小越容易在一次推送内到终态）。
    input_hash：**同一 agent 需要多簇时**显式传入不同值（uk_cluster_dedup 含 input_hash 列，
    缺省派生值只够一场景一簇 —— (c) 场景正需要「同 agent 多簇并行 claim」）。
    """
    async with AsyncSession(engine) as s:
        row = ErrorCluster(
            agent=agent, interface=IFACE, layer="L1", error_type="llm_timeout",
            input_hash=input_hash or hashlib.sha256(agent.encode()).hexdigest(),
            input_snapshot='{"question": "probe"}', input_truncated=0,
            error_msg="provider timeout", first_trace_id=f"{agent}-1",
            trigger_version="2026.09.09-r1", fix_version=fix_version,
            first_ts=NOW, latest_ts=NOW, count=1, generation=1, status=status,
            claimed_at=claimed_at, claim_due_ts=claim_due_ts, claim_k=claim_k,
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


async def _cluster_of(engine, cluster_id: int) -> ErrorCluster | None:
    async with AsyncSession(engine) as s:
        return await s.get(ErrorCluster, cluster_id)


async def _link_of(engine, link_id: int) -> ErrorCaseLink | None:
    async with AsyncSession(engine) as s:
        return await s.get(ErrorCaseLink, link_id)


async def _actions_of(engine, cluster_id: int) -> list[str]:
    return [c.action for c in await _convs_of(engine, cluster_id)]


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
    print("\n===== S-1 正常推送：落库 + 同事务判定写回（claim→fixed + link passed） =====")
    # 第 3 刀：落库即判，故场景造数必须是**可判现场**（cluster=claim ∧ pending link ∧ k 已固化），
    # 否则判定被守卫跳过、links_advanced 恒空——那种「绿」测不到任何东西。
    cid = await _seed_cluster(engine, "push-s1", status="claim", fix_version="1.5.0",
                              claimed_at=NOW, claim_due_ts=NOW + timedelta(days=14),
                              claim_k=1)
    lid = await _seed_link(engine, cid)
    status, body = await _push(client, trigger_signal_id=cid, run_id=f"{RUN_ID_PREFIX}1")
    runs = await _runs_of(engine, lid)
    convs = await _convs_of(engine, cid)
    rec = runs[0] if runs else None
    conv = next((c for c in convs if c.action == "regression_result"), None)
    cluster = await _cluster_of(engine, cid)
    link = await _link_of(engine, lid)
    # 判定写回断言（本刀新增，S-1 的核心价值）：link 离开 pending、cluster 收敛 fixed、
    # auto_fixed conv 落库——三者是「推送真的驱动了判定」的可观测证据。
    check("S-1 200 + links_advanced=[link] + run/conv 各一行（case_pass=1、系统动作）"
          " + 判定写回（link passed / cluster fixed / auto_fixed conv）",
          status == 200 and body["accepted"] is True and body["duplicated"] is False
          and body["links_advanced"] == [lid] and body["cases_dropped"] == 0
          and rec is not None and rec.id == body["run_record_id"]
          and rec.case_pass == 1 and rec.bound_version == "1.5.0"
          and rec.run_status == "completed"
          and (rec.raw_json or {}).get("finished_ts") == "2026-01-05T08:00:00Z"
          and (rec.raw_json or {}).get("prev_terminal_version") is None
          and conv is not None and conv.action == "regression_result"
          and conv.cluster_id == cid and conv.link_id == lid
          and conv.actor_user_id is None
          and link is not None and link.verify_status == "passed"
          and cluster is not None and cluster.status == "fixed"
          and "auto_fixed" in await _actions_of(engine, cid),
          f"{status} {body} runs={len(runs)} convs={[(c.action, c.link_id) for c in convs]} "
          f"link={link and link.verify_status} cluster={cluster and cluster.status}")


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
    # 第 3 刀：links_advanced 语义升级为「真发生终态迁移的 link」，故本场景用可判现场
    # （claim 簇 k=2）——单条 pass 只累计 K=1 不到终态，断言 [] 才是**真的**在测「未终态不报
    # 推进」，而不是被 cluster 非 claim 的守卫跳过（跳过时 [] 是无意义的假绿）。
    cid = await _seed_cluster(engine, "push-s6", status="claim", fix_version="1.5.0",
                              claimed_at=NOW, claim_due_ts=NOW + timedelta(days=14),
                              claim_k=2)
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
    link = await _link_of(engine, lid)
    cluster = await _cluster_of(engine, cid)
    check("S-6 cases_dropped=1 + 其余行正常落库（case_pass 取命中行 c-1=pass）+ raw 原样留档"
          " + 判定跑过但不达终态（links_advanced=[] / link pending / cluster claim 零终态 conv）",
          status == 200 and body["cases_dropped"] == 1 and body["links_advanced"] == []
          and len(runs) == 1 and rec.case_pass == 1
          and [c["case_type"] for c in raw_cases]
          == ["regression_error", "random_access", "regression_error"]
          and link is not None and link.verify_status == "pending"
          and cluster is not None and cluster.status == "claim"
          and await _actions_of(engine, cid) == ["regression_result"],
          f"{status} {body} runs={len(runs)} raw_cases={len(raw_cases)} "
          f"link={link and link.verify_status} cluster={cluster and cluster.status}"
          f" convs={await _actions_of(engine, cid)}")


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


def _pass_case(case_id="c-1") -> list[dict]:
    return [{"case_id": case_id, "case_type": "regression_error", "pass_fail": "pass"}]


async def s14_missing_prev_terminal_breaks_k(engine, client) -> None:
    """S-14 (a) 缺行中断：中间版本的结果推送丢失 → 判 gap，K **不累计**。

    现场：v1.0.0 pass（prev=null，首次）→ 中间版本 v2.0.0 的推送三次全败（online 无该行）
    → v3.0.0 pass 但载荷 prev_terminal_version=2.0.0，本地查无。
    推送源只有单值最大版本，**无法枚举中间版本**：若无该判据，online 只看得到
    v1(pass)+v3(pass) 两条相邻纯净 pass → k=2 直接判 fixed，簇被**静默误判修复**。
    k 取 2 是刻意的：移除判据即达 K 满 → 本场景断言转红（k=3 时缺版与误判都到不了 3，
    断不出规则在不在）——见文件头「已实测」注。
    """
    print("\n===== S-14 (a) 缺行中断：prev_terminal_version 本地无行 → gap 不累计 K =====")
    cid = await _seed_cluster(engine, "push-s14", status="claim", fix_version="1.0.0",
                              claimed_at=NOW, claim_due_ts=NOW + timedelta(days=14),
                              claim_k=2)
    lid = await _seed_link(engine, cid)
    s1, b1 = await _push(client, trigger_signal_id=cid, run_id=f"{RUN_ID_PREFIX}s14a1",
                         agent_version="1.0.0", agent_latest_version="1.0.0",
                         prev_terminal_version=None, cases=_pass_case())
    c1 = await _cluster_of(engine, cid)
    # v2.0.0 的推送**故意缺席**（模拟三推全败）→ 直接推 v3.0.0，prev 指向那个缺席版本
    s3, b3 = await _push(client, trigger_signal_id=cid, run_id=f"{RUN_ID_PREFIX}s14a3",
                         agent_version="3.0.0", agent_latest_version="3.0.0",
                         prev_terminal_version="2.0.0", cases=_pass_case())
    runs = await _runs_of(engine, lid)
    c3 = await _cluster_of(engine, cid)
    link3 = await _link_of(engine, lid)
    check("S-14 (a) v1 pass（K=1）后 v2 推送丢失、v3 pass → 判 gap：cluster 保持 claim /"
          " link 仍 pending / K 不累计（否则 k=2 会误判 fixed）",
          s1 == 200 and b1["links_advanced"] == [] and c1.status == "claim"
          and s3 == 200 and b3["duplicated"] is False and b3["links_advanced"] == []
          and len(runs) == 2
          and c3.status == "claim" and link3.verify_status == "pending"
          and "auto_fixed" not in await _actions_of(engine, cid),
          f"v1={s1} {b1} v3={s3} {b3} status={c3.status} "
          f"link={link3.verify_status} runs={len(runs)}")


async def s15_prev_terminal_present_accumulates(engine, client) -> None:
    """S-15 (b) 反假绿对照：同形态但中间版本**本地有行** → 正常累计到 K 满 → fixed。

    与 S-14 (a) 只差一个条件（v2.0.0 的行到底在不在），结论必须相反——这才证明 S-14 的
    「保持 claim」是缺行中断判据生效，不是链路整体不工作（防假绿）。
    """
    print("\n===== S-15 (b) 对照：中间版本本地有行 → 正常累计 K 满 → fixed =====")
    cid = await _seed_cluster(engine, "push-s15", status="claim", fix_version="1.0.0",
                              claimed_at=NOW, claim_due_ts=NOW + timedelta(days=14),
                              claim_k=3)
    lid = await _seed_link(engine, cid)
    outs = []
    for ver, prev in (("1.0.0", None), ("2.0.0", "1.0.0"), ("3.0.0", "2.0.0")):
        outs.append(await _push(client, trigger_signal_id=cid,
                                run_id=f"{RUN_ID_PREFIX}s15{ver}",
                                agent_version=ver, agent_latest_version="3.0.0",
                                prev_terminal_version=prev, cases=_pass_case()))
    cluster = await _cluster_of(engine, cid)
    link = await _link_of(engine, lid)
    runs = await _runs_of(engine, lid)
    # 中途两推必须仍未收敛（K 逐版累计而非一次到位），末推才迁移——否则「累计」是假的
    check("S-15 (b) 三版链式 pass（prev 逐版命中本地行）→ 前两推 pending / 末推 fixed_auto",
          all(s == 200 for s, _ in outs)
          and [b["links_advanced"] for _, b in outs] == [[], [], [lid]]
          and len(runs) == 3
          and cluster.status == "fixed" and link.verify_status == "passed"
          and "auto_fixed" in await _actions_of(engine, cid),
          f"advanced={[b['links_advanced'] for _, b in outs]} status={cluster.status} "
          f"link={link.verify_status} runs={len(runs)}")


# ---------- 本批：判定安全网（(a) 补判 / (b) 降级 / (c) agent 级 gap / (d) 老格式） ----------


async def s16_push_before_claim_then_rejudge(engine, client, token) -> None:
    """S-16 (a) 顺序一：推送先到、cluster 尚未 claim → 判定被守卫跳过 → **rejudge 补判**。

    这是本批的核心现场（建簇 open → ≤60s 自动组装 → offline 拉走 → 推结果时 cluster 仍
    open）。判定被 `cluster.status=='claim'` 守卫跳过后，**不会再有事件来驱动这次判定**
    （认领不是事件），没有 rejudge 就永久 pending —— 本场景即该闭环的端到端证据。
    """
    print("\n===== S-16 (a) 顺序一：推送先到（cluster 非 claim）→ rejudge 补判收敛 =====")
    cid = await _seed_cluster(engine, "push-s16", status="open", claim_k=1)
    lid = await _seed_link(engine, cid)
    s1, b1 = await _push(client, trigger_signal_id=cid, run_id=f"{RUN_ID_PREFIX}s16",
                         agent_version="1.5.0", agent_latest_version="1.5.0",
                         prev_terminal_version=None, cases=_pass_case())
    c1 = await _cluster_of(engine, cid)
    l1 = await _link_of(engine, lid)
    runs1 = await _runs_of(engine, lid)
    # 认领（真实路径，走端点）：fix_version 是 claim 产物，没有它判定算不出 K
    r = await client.post(f"{API}/backflow/clusters/{cid}/claim",
                          json={"fix_version": "1.5.0", "k": 1}, headers=_hdr(token))
    judged = await run_rejudge(engine)
    cluster = await _cluster_of(engine, cid)
    link = await _link_of(engine, lid)
    check("S-16 推送先到：200 + links_advanced=[]（守卫跳过）+ 数据照落 + 簇仍 open/link pending；"
          "claim 后 rejudge 一轮 → link passed / cluster fixed / auto_fixed 落库",
          s1 == 200 and b1["duplicated"] is False and b1["links_advanced"] == []
          and len(runs1) == 1
          and c1.status == "open" and l1.verify_status == "pending"
          and r.status_code == 200 and r.json()["claim_k"] == 1
          and judged >= 1
          and link.verify_status == "passed" and cluster.status == "fixed"
          and "auto_fixed" in await _actions_of(engine, cid),
          f"push={s1} {b1} claim={r.status_code} judged={judged} "
          f"link={link.verify_status} cluster={cluster.status} "
          f"convs={await _actions_of(engine, cid)}")


async def s17_claim_before_push_judged_without_job(engine, client) -> None:
    """S-17 (a) 顺序二（S-16 的对照）：cluster 已 claim 时推送到达 → **推送端点内立即判掉**。

    与 S-16 只差「推送时簇是否已 claim」一个维度，结论必须相反（一边要等 job、一边立刻收敛）
    ——证明 S-16 的「等 rejudge」是守卫语义使然，不是判定链路整体不工作。
    """
    print("\n===== S-17 (a) 顺序二：cluster 先 claim → 推送端点内立即收敛（不等 job） =====")
    cid = await _seed_cluster(engine, "push-s17", status="claim", fix_version="1.5.0",
                              claimed_at=NOW, claim_due_ts=NOW + timedelta(days=14),
                              claim_k=1)
    lid = await _seed_link(engine, cid)
    s1, b1 = await _push(client, trigger_signal_id=cid, run_id=f"{RUN_ID_PREFIX}s17",
                         agent_version="1.5.0", agent_latest_version="1.5.0",
                         prev_terminal_version=None, cases=_pass_case())
    cluster = await _cluster_of(engine, cid)
    link = await _link_of(engine, lid)
    check("S-17 200 + links_advanced=[link]（同事务判定写回）+ link passed / cluster fixed",
          s1 == 200 and b1["links_advanced"] == [lid]
          and link.verify_status == "passed" and cluster.status == "fixed"
          and "auto_fixed" in await _actions_of(engine, cid),
          f"{s1} {b1} link={link.verify_status} cluster={cluster.status}")


async def s18_judge_exception_degrades_row_survives(engine, client) -> None:
    """S-18 (b) 判定中途抛**DB 级**异常 → 降级：半态被回退、行照落、200、之后 rejudge 补判。

    桩的形态刻意做成「先写一半（把 link 改成 superseded，模拟判定链边判边写）再抛真 DB
    错误（查不存在的表）」——**只有这种形态才测得到 savepoint 的价值**：MySQL 的语句级报错
    **不**作废整个事务，裸调用时 commit 照样成功（本条第一版只断言「抛错后仍 200 + 行落库」，
    去掉 savepoint 后**依旧全绿** → 断言没有钉住任何东西，等于假绿）。savepoint 真正保证的是
    「判定自己的写全进全出」：去掉它 → 那半笔 link=superseded 会被 commit（半态落库）、
    rejudge 也再找不到 pending link → 本场景转红。
    """
    print("\n===== S-18 (b) 判定 DB 异常 → 降级（savepoint 保住结果行）→ rejudge 补判 =====")
    cid = await _seed_cluster(engine, "push-s18", status="claim", fix_version="1.5.0",
                              claimed_at=NOW, claim_due_ts=NOW + timedelta(days=14),
                              claim_k=1)
    lid = await _seed_link(engine, cid)
    original = backflow_api.judge_link

    async def _boom(session, *, cluster, link):
        # 真判定链是**边判边写**（link/cluster CAS + conv），且可能在链的后半段才炸 —— 故桩
        # 必须先写一半再抛，否则测不出「半态被提交」（MySQL 语句级报错**不**回滚整个事务，
        # 故单靠「抛错后 commit 还能不能成」测不出 savepoint 的价值，实测踩过）。
        # 用 text 而非 ORM update()：ORM 版默认会去同步 session 内的同名对象（expired 时
        # 触发惰性 refresh → MissingGreenlet 报错，实测踩过），这里只要一笔真写。
        await session.execute(
            text("UPDATE error_case_link SET verify_status='superseded' WHERE id=:i"),
            {"i": link.id})
        await session.execute(text("SELECT 1 FROM probe_no_such_table"))  # ProgrammingError

    backflow_api.judge_link = _boom
    try:
        s1, b1 = await _push(client, trigger_signal_id=cid, run_id=f"{RUN_ID_PREFIX}s18",
                             agent_version="1.5.0", agent_latest_version="1.5.0",
                             prev_terminal_version=None, cases=_pass_case())
    finally:
        backflow_api.judge_link = original
    runs = await _runs_of(engine, lid)
    c1 = await _cluster_of(engine, cid)
    l1 = await _link_of(engine, lid)
    convs = await _actions_of(engine, cid)
    judged = await run_rejudge(engine)
    cluster = await _cluster_of(engine, cid)
    link = await _link_of(engine, lid)
    check("S-18 判定抛 DB 异常 → 响应仍 200 + run 行已落库（savepoint 只回退判定）+ 簇未迁移；"
          "恢复后 rejudge 补判 → fixed",
          s1 == 200 and b1["accepted"] is True and b1["links_advanced"] == []
          and len(runs) == 1 and runs[0].run_id == f"{RUN_ID_PREFIX}s18"
          and c1.status == "claim" and l1.verify_status == "pending"
          and "auto_fixed" not in convs and "regression_result" in convs
          and judged >= 1 and link.verify_status == "passed" and cluster.status == "fixed",
          f"{s1} {b1} runs={len(runs)} 降级后 cluster={c1.status} link={l1.verify_status} "
          f"convs={convs} judged={judged} 补判后 cluster={cluster.status}/"
          f"link={link.verify_status}")


async def s19_agent_level_gap_no_false_positive(engine, client, token) -> None:
    """S-19 (c) 缺行中断判据改 **agent 级**：同 agent 两簇并行 claim 不产生假 gap + 真 gap 对照。

    现场：同一 agent 三个 claim 簇并行。
    - 簇 A 收 v1.0.0（prev=null）；
    - 簇 B 收 v2.0.0 且 prev=v1.0.0 —— v1 的行**不在 B 的 link 上**（在 A 上）。判据若按
      本 link 行集查 → 判假 gap → B 永远推不进（k=1 下本应一次收敛）；按 agent 级查 → 无 gap
      → 正常累计 → B 收敛 fixed。**这是「静默拖住推进且无 UI 可见面」的那个 bug 现场**。
    - 簇 C 收一条 prev 指向 **9.9.9**（该 agent 全局**从未收到过**任何 9.9.9 行）→ **仍判 gap**：
      证明改全局判据**没有削弱**防假连续（该版本的行在全库都不存在，与「v2 推送真丢」同形）。
      注：C 的 prev 不能取「本场景前面刚推过的版本」——簇 B 落库的 v2.0.0 行本身就是 agent 级
      可见事实，取它就**不是**真 gap，断言会因错误理由而绿/红。
    顺带覆盖 (g) 读面派生标记 result_gap_suspected 的两态（C=true / A=false 且 A 是 pending link）。
    """
    print("\n===== S-19 (c) agent 级 gap：并行 claim 不假报 + 真丢推送仍判 gap =====")
    agent = "push-s19"
    ca = await _seed_cluster(engine, agent, status="claim", fix_version="1.0.0",
                             claimed_at=NOW, claim_due_ts=NOW + timedelta(days=14),
                             claim_k=2, input_hash=hashlib.sha256(b"s19a").hexdigest())
    await _seed_link(engine, ca)  # 簇 A 的 link（本场景只需其行落在 agent 级集合里）
    cb = await _seed_cluster(engine, agent, status="claim", fix_version="1.0.0",
                             claimed_at=NOW, claim_due_ts=NOW + timedelta(days=14),
                             claim_k=1, input_hash=hashlib.sha256(b"s19b").hexdigest())
    lb = await _seed_link(engine, cb)
    cc = await _seed_cluster(engine, agent, status="claim", fix_version="1.0.0",
                             claimed_at=NOW, claim_due_ts=NOW + timedelta(days=14),
                             claim_k=2, input_hash=hashlib.sha256(b"s19c").hexdigest())
    lc = await _seed_link(engine, cc)
    sa, ba = await _push(client, trigger_signal_id=ca, run_id=f"{RUN_ID_PREFIX}s19a",
                         agent_version="1.0.0", agent_latest_version="1.0.0",
                         prev_terminal_version=None, cases=_pass_case())
    sb, bb = await _push(client, trigger_signal_id=cb, run_id=f"{RUN_ID_PREFIX}s19b",
                         agent_version="2.0.0", agent_latest_version="2.0.0",
                         prev_terminal_version="1.0.0", cases=_pass_case())
    sc, bc = await _push(client, trigger_signal_id=cc, run_id=f"{RUN_ID_PREFIX}s19c",
                         agent_version="3.0.0", agent_latest_version="3.0.0",
                         prev_terminal_version="9.9.9", cases=_pass_case())
    cl_b = await _cluster_of(engine, cb)
    lk_b = await _link_of(engine, lb)
    cl_c = await _cluster_of(engine, cc)
    lk_c = await _link_of(engine, lc)
    _, da = await _detail(client, ca, token)
    _, dc = await _detail(client, cc, token)
    check("S-19 (c) 簇 B：prev=v1（v1 行在**同 agent 另一簇**上）→ 不判假 gap → k=1 收敛 fixed；"
          "簇 C：prev=9.9.9 而全库无该版本行 → 真 gap 保持 claim/pending（防假连续未削弱）；"
          "读面标记 result_gap_suspected = A:false / C:true",
          sa == 200 and ba["links_advanced"] == [] and sb == 200
          and bb["links_advanced"] == [lb] and cl_b.status == "fixed"
          and lk_b.verify_status == "passed"
          and sc == 200 and bc["links_advanced"] == []
          and cl_c.status == "claim" and lk_c.verify_status == "pending"
          and "auto_fixed" not in await _actions_of(engine, cc)
          and da.get("result_gap_suspected") is False
          and dc.get("result_gap_suspected") is True,
          f"A={sa} {ba} B={sb} {bb} B.status={cl_b.status} B.link={lk_b.verify_status} "
          f"C={sc} {bc} C.status={cl_c.status} C.link={lk_c.verify_status} "
          f"gap_mark A={da.get('result_gap_suspected')} C={dc.get('result_gap_suspected')}")


async def s20_legacy_row_without_cases_not_missing(engine, client) -> None:
    """S-20 (d) 第 2 刀期老格式行（raw_json 无 `cases` 键）→ 不可判：保持 pending（不判 missing）。

    现场：link 上先有一条老格式 v1.5.0 行（只写了列 case_pass），再推一条逐 case v2.0.0 pass。
    k=1 下若把老行当 missing（= 断链、不清零不累计）跨过 → v2 的纯净 pass 直接算满 K →
    **假 fixed**（等于用「不知道 v1 结果」换来「修复」）。判据必须停在不可判版本上。
    库内**不做数据迁移**（v1 上线前无真实流量），故该形态只可能来自历史行 —— 本场景直接造行。
    """
    print("\n===== S-20 (d) 老格式行（无 cases 键）→ 不可判保持 pending（不判 missing） =====")
    cid = await _seed_cluster(engine, "push-s20", status="claim", fix_version="1.5.0",
                              claimed_at=NOW, claim_due_ts=NOW + timedelta(days=14),
                              claim_k=1)
    lid = await _seed_link(engine, cid)
    async with AsyncSession(engine) as s:  # 老格式行：raw 只有列值，无 cases 键
        s.add(VerifyRunRecord(link_id=lid, run_id=f"{RUN_ID_PREFIX}s20legacy",
                              bound_version="1.5.0", case_pass=0,
                              run_status="completed", raw_json={"case_pass": 0}))
        await s.commit()
    s2, b2 = await _push(client, trigger_signal_id=cid, run_id=f"{RUN_ID_PREFIX}s20",
                         agent_version="2.0.0", agent_latest_version="2.0.0",
                         prev_terminal_version=None, cases=_pass_case())
    cluster = await _cluster_of(engine, cid)
    link = await _link_of(engine, lid)
    runs = await _runs_of(engine, lid)
    check("S-20 老格式行在前 → 保持 pending（cluster 仍 claim / link 仍 pending / 无 auto_fixed）"
          "，且新格式行照常落库（200）",
          s2 == 200 and b2["duplicated"] is False and b2["links_advanced"] == []
          and len(runs) == 2
          and cluster.status == "claim" and link.verify_status == "pending"
          and "auto_fixed" not in await _actions_of(engine, cid),
          f"{s2} {b2} runs={len(runs)} cluster={cluster.status} link={link.verify_status} "
          f"convs={await _actions_of(engine, cid)}")


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
            await s14_missing_prev_terminal_breaks_k(engine, client)
            await s15_prev_terminal_present_accumulates(engine, client)
            # 本批（判定安全网）：S-16/S-19 会各跑一轮 rejudge，而 run_rejudge **全局扫描**
            # 所有 claim 簇 + pending link —— 排在其他场景之后，避免它的补判改变前面场景的
            # 断言现场（尤其 S-14「保持 claim」那类「什么都没发生」的断言）。
            await s16_push_before_claim_then_rejudge(engine, client, token)
            await s17_claim_before_push_judged_without_job(engine, client)
            await s18_judge_exception_degrades_row_survives(engine, client)
            await s19_agent_level_gap_no_false_positive(engine, client, token)
            await s20_legacy_row_without_cases_not_missing(engine, client)
    finally:
        await _cleanup(engine)
        await engine.dispose()
    print("\n===== push_probe 结果 =====")
    if FAILURES:
        print(f"FAIL: {len(FAILURES)}/{len(CHECKS)} 项失败 → {FAILURES}")
        sys.exit(1)
    print(f"全绿：push 结果推送接收面接收+判定写回/幂等/orphan/校验/丢行/overdue 判据/"
          f"缺行中断 {len(CHECKS)}/{len(CHECKS)} 场景通过")


if __name__ == "__main__":
    asyncio.run(main())
