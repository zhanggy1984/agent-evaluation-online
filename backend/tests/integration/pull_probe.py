"""P2-3 pull-API/ack/invalidate/requeue 集成探针（detail §7.2/§7.3/§7.4/§8.4/§8.7，T-3.3）。
容器内 `docker exec obs-backend` 运行：

    docker exec obs-backend python /app/tests/integration/pull_probe.py

前置：obs-backend 已 up（DB_HOST=mysql 容器内 alias）。形态升级 = **HTTP 级**：探针自建
async engine + `create_app(Settings(app_env=test, evaluator_service_secret=…))` +
`dependency_overrides[get_session]` 挂真库 AsyncSession → httpx ASGITransport 全 HTTP 打端点
（真实鉴权 header / secret / 错误体 R3）。DB 断言另起真 session 读。

覆盖（单测纯函数装不下的实库语义：多行 keyset 分页 / CAS / 真词表回填 / 防抖锚 / conv 落库）：
  P-1  pull 空集（agent 无 assembled link）
  P-2  组装好 assembled link 拉取：envelope 逐字段 + 顶层 assembled_ts(ISO8601 UTC)
  P-3  since_ts + agent + limit + next_token 分页（(assembled_ts,id) 升序、跨页无重漏、增量边界）
  P-4  ack draft → 幂等重放 200 → assembled 队列不再含
  P-5  active 缺 case_id → ERR_CLUSTER_0003 带当前状态(R3)；补 case_id → active(case_id 落库)
  P-6  ack invalidated(online_content_gap) → invalidated + invalidate_reason；重放 200(幂等)
  P-7  R2：invalidated(offline_cap_gap)+case_id → active 放行清标注；content_gap 行 → 400(R3)
  P-8  未知 payload_id → ERR_PULL_0003(404)
  P-9  人工 invalidate：assembled → invalidated(manual, invalidated_by=admin)；active 拒绝；
       viewer token → ERR_AUTH_0002(403)
  P-10 requeue 复位：payload_id 复用 + payload_json 重填(wordlist_v 升) + assembled_ts 刷新 +
       清 reason；since_ts 旧水位重拉可见（E-22）
  P-11 requeue 守卫：fixed cluster 拒(superseded+reopen)；防抖 <5min 拒
  P-12 requeue-batch：content_gap×2 requeued + cap_gap 滤外 + fresh 防抖 skip + conv 汇总
  P-13 E-15：同 payload 连续双 ack（active）均 200、终态恰一次迁移

隔离：agent 前缀 pul-（≤64），开头/结尾清理（agent/dict_config/cluster/link/conv + 探针
用户 + requeue-batch 聚合 conv）。退出码全绿 0。
"""
import asyncio
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app")

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import delete, select, update  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.backflow.ack import iso_utc  # noqa: E402
from app.converter.envelope import assemble_cluster  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.core.db import get_session  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.agent import Agent  # noqa: E402
from app.models.config import DictConfig  # noqa: E402
from app.models.error_flow import ConversionRecord, ErrorCaseLink, ErrorCluster  # noqa: E402
from app.models.user import User  # noqa: E402

FAILURES: list[str] = []
IFACE = "POST /api/probe/{id}"
NOW = datetime.now(timezone.utc).replace(tzinfo=None)
DICT_KEY = "fallback_utterance"
WORDS_V1 = ["抱歉，暂时无法回答"]
WORDS_V2 = ["抱歉，暂时无法回答", "系统繁忙，请稍后再试"]
_SECRET = "probe-pull-secret"
_JWT = "probe-jwt-0123456789abcdefghijklmnopqrstuvwxyz"
ADMIN = "pul-probe-admin"
VIEWER = "pul-viewer"
API = "/api/v1"


def check(name: str, ok: bool, detail: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    if not ok:
        FAILURES.append(name)


# ---------- DB 基建 ----------


async def _cleanup(engine) -> None:
    """清 pul-% 残留：conv→link→cluster + requeue-batch 聚合 conv + user + dict_config→agent。"""
    async with AsyncSession(engine) as s:
        sub = select(ErrorCluster.id).where(ErrorCluster.agent.like("pul-%"))
        await s.execute(delete(ConversionRecord).where(ConversionRecord.cluster_id.in_(sub)))
        await s.execute(delete(ErrorCaseLink).where(ErrorCaseLink.cluster_id.in_(sub)))
        await s.execute(delete(ErrorCluster).where(ErrorCluster.agent.like("pul-%")))
        await s.execute(delete(ConversionRecord).where(  # 批量聚合 conv（cluster_id NULL）
            ConversionRecord.cluster_id.is_(None),
            ConversionRecord.action == "requeue",
        ))
        await s.execute(delete(User).where(User.username.in_((ADMIN, VIEWER))))
        ag = select(Agent.id).where(Agent.name.like("pul-%"))
        await s.execute(delete(DictConfig).where(DictConfig.agent_id.in_(ag)))
        await s.execute(delete(Agent).where(Agent.name.like("pul-%")))
        await s.commit()


async def _ensure_user(engine, name: str, role: str) -> int:
    async with AsyncSession(engine) as s:
        u = User(username=name, password_hash="x" * 60, role=role, status=1)
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
        return uid


async def _seed_agent(engine, name: str, *, words: list | None = WORDS_V1, version: int = 1) -> int:
    async with AsyncSession(engine) as s:
        agent = Agent(name=name, display_name=name, base_url=None, enable=1,
                      route_source="auto_register", backflow_allow=1)
        s.add(agent)
        await s.flush()
        s.add(DictConfig(agent_id=agent.id, config_key=DICT_KEY,
                         config_value=words, version=version, updated_by="probe"))
        aid = agent.id
        await s.commit()
        return aid


async def _bump_wordlist(engine, agent: str, *, words: list, version: int) -> None:
    """同 key UPDATE 词表（uk_dc：不重建行）——requeue 内容缺愈以新词表重填。"""
    async with AsyncSession(engine) as s:
        agent_id = await s.scalar(select(Agent.id).where(Agent.name == agent))
        await s.execute(update(DictConfig)
                        .where(DictConfig.agent_id == agent_id,
                               DictConfig.config_key == DICT_KEY)
                        .values(config_value=words, version=version))
        await s.commit()


async def _seed_cluster(engine, agent: str, *, snapshot: str, status="open",
                        error_type="llm_timeout") -> int:
    """落 cluster；input_hash 由 snapshot 派生（同 agent 多簇不撞 uk_cluster_dedup）。"""
    input_hash = hashlib.sha256(f"{agent}|{snapshot}".encode()).hexdigest()
    async with AsyncSession(engine) as s:
        row = ErrorCluster(
            agent=agent, interface=IFACE, layer="L1", error_type=error_type,
            input_hash=input_hash, input_snapshot=snapshot, input_truncated=0,
            error_msg="provider timeout", first_trace_id=f"pul-{agent}-1",
            trigger_version="2026.09.09-r1", fix_version=None,
            first_ts=NOW, latest_ts=NOW, count=1, generation=1, status=status,
        )
        s.add(row)
        await s.flush()
        cid = row.id
        await s.commit()
        return cid


async def _seed_assembled(engine, agent: str, snapshot: str, *, status="open") -> dict:
    """种 open cluster + assemble → {link_id, payload_id, cluster_id}（assemble conv 已落）。"""
    cid = await _seed_cluster(engine, agent, snapshot=snapshot, status=status)
    async with AsyncSession(engine) as s:
        cluster = (await s.scalars(
            select(ErrorCluster).where(ErrorCluster.id == cid))).one()
        await assemble_cluster(s, cluster)
        await s.commit()
    async with AsyncSession(engine) as s:
        link = (await s.scalars(
            select(ErrorCaseLink).where(ErrorCaseLink.cluster_id == cid))).one()
        return {"link_id": link.id, "payload_id": link.payload_id, "cluster_id": cid}


async def _backdate(engine, link_id: int, minutes: int = 10) -> None:
    """assembled_ts 拨回 now-Xmin：requeue 防抖锚 ≥5min（探针不等真实时钟）。"""
    async with AsyncSession(engine) as s:
        await s.execute(update(ErrorCaseLink).where(ErrorCaseLink.id == link_id)
                        .values(assembled_ts=NOW - timedelta(minutes=minutes)))
        await s.commit()


async def _link_by_payload(engine, payload_id: str):
    async with AsyncSession(engine) as s:
        return await s.scalar(select(ErrorCaseLink).where(ErrorCaseLink.payload_id == payload_id))


async def _link_by_id(engine, link_id: int):
    async with AsyncSession(engine) as s:
        return await s.get(ErrorCaseLink, link_id)


async def _link_env(engine, link_id: int) -> dict:
    lk = await _link_by_id(engine, link_id)
    return json.loads(lk.payload_json)


async def _set_cluster_status(engine, cluster_id: int, status: str) -> None:
    async with AsyncSession(engine) as s:
        await s.execute(update(ErrorCluster).where(ErrorCluster.id == cluster_id)
                        .values(status=status))
        await s.commit()


# ---------- HTTP 壳 ----------


async def _pull(client, agent, *, since_ts=None, limit=100, nxt=None):
    body = {"schema_version": "1.0", "case_type": "regression_error", "limit": limit,
            "agent": agent}
    if since_ts:
        body["since_ts"] = since_ts
    if nxt:
        body["next_token"] = nxt
    r = await client.post(f"{API}/pull/payloads", json=body,
                          headers={"Authorization": f"Bearer {_SECRET}"})
    return r.status_code, r.json()


async def _ack(client, payload_id, action, *, case_id=None, reason=None):
    body = {"payload_id": payload_id, "action": action}
    if case_id:
        body["case_id"] = case_id
    if reason:
        body["reason"] = reason
    r = await client.post(f"{API}/pull/ack", json=body,
                          headers={"Authorization": f"Bearer {_SECRET}"})
    return r.status_code, r.json()


def _hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _invalidate(client, link_id, token, *, reason=None):
    body = {} if reason is None else {"reason": reason}
    resp = await client.post(f"{API}/backflow/links/{link_id}/invalidate", json=body,
                             headers=_hdr(token))
    return resp.status_code, resp.json()


async def _requeue(client, link_id, token):
    resp = await client.post(f"{API}/backflow/links/{link_id}/requeue",
                             headers=_hdr(token))
    return resp.status_code, resp.json()


async def _batch(client, token, *, agent=None):
    f = {"invalidate_reason": "online_content_gap"}
    if agent:
        f["agent"] = agent
    resp = await client.post(f"{API}/backflow/links/requeue-batch",
                             json={"filter": f}, headers=_hdr(token))
    return resp.status_code, resp.json()


# ---------- P 场景 ----------


async def p1_empty(engine, client) -> None:
    print("\n===== P-1 pull 空集（无 assembled link） =====")
    await _seed_agent(engine, "pul-p1")
    status, body = await _pull(client, "pul-p1")
    check("P-1 无 link → 200 空集",
          status == 200 and body == {"payloads": [], "next_token": None}, f"{status} {body}")


async def p2_pull_fields(engine, client) -> None:
    print("\n===== P-2 assembled link 拉取：envelope 逐字段 + assembled_ts ISO =====")
    await _seed_agent(engine, "pul-p2", words=WORDS_V1, version=5)
    mk = await _seed_assembled(engine, "pul-p2", '{"question": "q"}')
    status, body = await _pull(client, "pul-p2")
    assert status == 200
    payloads = body["payloads"]
    if not payloads:
        check("P-2 拉取非空", False, "payloads 空")
        return
    env = payloads[0]
    lk = await _link_by_id(engine, mk["link_id"])
    check("P-2 拉 1 条 + envelope 源/词表/顶层 assembled_ts(ISO Z)",
          len(payloads) == 1 and body["next_token"] is None
          and env["schema_version"] == "1.0" and env["case_type"] == "regression_error"
          and env["payload_id"] == lk.payload_id
          and env["source"]["agent"] == "pul-p2"
          and env["source"]["cluster_id"] == mk["cluster_id"]
          and env["versions"]["trigger_version"] == "2026.09.09-r1"
          and env["no_fallback_config"]["words"] == WORDS_V1
          and env["no_fallback_config"]["wordlist_version"] == 5
          and env["assert"]["no_fallback"]["config_ref"]["wordlist_version"] == 5
          and isinstance(env.get("assembled_ts"), str) and env["assembled_ts"].endswith("Z"),
          f"payloads={len(payloads)} assembled_ts={env.get('assembled_ts')}")


async def p3_pagination(engine, client) -> None:
    print("\n===== P-3 since_ts+agent+limit+next_token 分页（keyset 升序无重漏） =====")
    agent = "pul-p3"
    await _seed_agent(engine, agent)
    mks = []
    for i in range(3):
        mks.append(await _seed_assembled(engine, agent, '{"q": "%d"}' % i))
    await _seed_agent(engine, "pul-p3x")  # 干扰 agent：卷不进来
    await _seed_assembled(engine, "pul-p3x", '{"q": "noise"}')
    s1, b1 = await _pull(client, agent, limit=2)
    assert s1 == 200
    s2, b2 = await _pull(client, agent, limit=2, nxt=b1["next_token"])
    page1 = b1["payloads"]
    page2 = b2["payloads"]
    ids = [p["source"]["cluster_id"] for p in page1 + page2]
    check("P-3 页 1=2 带 token / 页 2=1 无 token，合并恰 3 无重漏",
          len(page1) == 2 and b1["next_token"] is not None
          and len(page2) == 1 and b2["next_token"] is None
          and sorted(ids) == sorted(m["cluster_id"] for m in mks),
          f"p1={len(page1)} p2={len(page2)} ids={ids}")
    check("P-3 agent 过滤排除他 agent link",
          all(p["source"]["agent"] == agent for p in page1 + page2), "有污染")
    first_lk = await _link_by_id(engine, mks[0]["link_id"])
    last_lk = await _link_by_id(engine, mks[2]["link_id"])
    low_iso = iso_utc(first_lk.assembled_ts - timedelta(milliseconds=1))
    high_iso = iso_utc(last_lk.assembled_ts + timedelta(milliseconds=1))
    s3, b3 = await _pull(client, agent, since_ts=low_iso)
    s4, b4 = await _pull(client, agent, since_ts=high_iso)
    check("P-3 since_ts 增量边界（最早-1ms 全含 / 最晚+1ms 空）",
          s3 == 200 and len(b3["payloads"]) == 3
          and s4 == 200 and b4["payloads"] == [],
          f"since_low={len(b3['payloads'])} since_high={len(b4['payloads'])}")


async def p4_ack_draft_idempotent(engine, client) -> None:
    print("\n===== P-4 ack draft → 幂等重放 200 → 不再可拉 =====")
    await _seed_agent(engine, "pul-p4")
    mk = await _seed_assembled(engine, "pul-p4", '{"q": "q"}')
    s1, b1 = await _ack(client, mk["payload_id"], "draft", case_id="case-p4")
    s2, b2 = await _ack(client, mk["payload_id"], "draft", case_id="case-p4")  # 重放幂等 E-15
    lk = await _link_by_payload(engine, mk["payload_id"])
    check("P-4 draft 首次+重放均 200 且落库 case_id",
          s1 == 200 and b1["offline_status"] == "draft"
          and s2 == 200 and b2["offline_status"] == "draft"
          and lk.offline_status == "draft" and lk.case_id == "case-p4",
          f"{s1}/{s2} off={lk.offline_status}")
    s3, b3 = await _pull(client, "pul-p4")
    check("P-4 draft 后不再被 assembled 队列拉取",
          b3["payloads"] == [], f"got={len(b3['payloads'])}")


async def p5_ack_active_requires_case_id(engine, client) -> None:
    print("\n===== P-5 active 缺 case_id → R3 400；补 → active(case_id 落库) =====")
    await _seed_agent(engine, "pul-p5")
    mk = await _seed_assembled(engine, "pul-p5", '{"q": "q"}')
    pid = mk["payload_id"]
    s1, b1 = await _ack(client, pid, "active")
    check("P-5 active 缺 case_id → ERR_CLUSTER_0003(400) 带 R3 当前状态",
          s1 == 400 and b1["code"] == "ERR_CLUSTER_0003"
          and b1.get("offline_status") == "assembled" and b1.get("invalidate_reason") == "",
          f"{s1} {b1}")
    s2, b2 = await _ack(client, pid, "active", case_id="case-p5")
    lk = await _link_by_payload(engine, pid)
    check("P-5 补 case_id → active(case_id 落库)",
          s2 == 200 and b2["offline_status"] == "active"
          and lk.offline_status == "active" and lk.case_id == "case-p5",
          f"{s2} {b2}")


async def p6_ack_invalidated_replay(engine, client) -> None:
    print("\n===== P-6 ack invalidated(online_content_gap) → invalidated；重放 200 =====")
    await _seed_agent(engine, "pul-p6")
    mk = await _seed_assembled(engine, "pul-p6", '{"q": "q"}')
    pid = mk["payload_id"]
    s1, b1 = await _ack(client, pid, "invalidated", reason="online_content_gap")
    s2, b2 = await _ack(client, pid, "invalidated", reason="online_content_gap")
    lk = await _link_by_payload(engine, pid)
    check("P-6 驳回 + 重放幂等 200，invalidate_reason 落库",
          s1 == 200 and b1["offline_status"] == "invalidated"
          and s2 == 200 and b2["offline_status"] == "invalidated"
          and lk.offline_status == "invalidated"
          and lk.invalidate_reason == "online_content_gap" and lk.verify_status == "pending",
          f"{s1}/{s2} reason={lk.invalidate_reason}")


async def p7_r2_exception(engine, client) -> None:
    print("\n===== P-7 R2：offline_cap_gap 行 → active 放行；content_gap 行 → 400 =====")
    await _seed_agent(engine, "pul-p7ok")
    ok = await _seed_assembled(engine, "pul-p7ok", '{"q": "r2ok"}')
    assert (await _ack(client, ok["payload_id"], "invalidated", reason="offline_cap_gap"))[0] == 200
    s, b = await _ack(client, ok["payload_id"], "active", case_id="case-r2")
    lk = await _link_by_payload(engine, ok["payload_id"])
    check("P-7 R2 放行：active + case_id + 清失效标注",
          s == 200 and b["offline_status"] == "active"
          and lk.offline_status == "active" and lk.case_id == "case-r2"
          and lk.invalidate_reason is None and lk.invalidated_by is None,
          f"{s} {b}")
    await _seed_agent(engine, "pul-p7no")
    no = await _seed_assembled(engine, "pul-p7no", '{"q": "r2no"}')
    assert (await _ack(client, no["payload_id"], "invalidated",
                       reason="online_content_gap"))[0] == 200
    s2, b2 = await _ack(client, no["payload_id"], "active", case_id="case-r2",
                        reason="offline_cap_gap")  # incoming reason 不兜底（gate 现行标注）
    check("P-7 content_gap 行 → ERR_CLUSTER_0003(400 带 R3 状态)",
          s2 == 400 and b2["code"] == "ERR_CLUSTER_0003"
          and b2.get("offline_status") == "invalidated"
          and b2.get("invalidate_reason") == "online_content_gap",
          f"{s2} {b2}")


async def p8_unknown_payload(engine, client) -> None:
    print("\n===== P-8 未知 payload_id → ERR_PULL_0003(404) =====")
    s, b = await _ack(client, "pl-nonexistent-0000", "draft")
    check("P-8 未知 payload 404", s == 404 and b["code"] == "ERR_PULL_0003", f"{s} {b}")


async def p9_admin_invalidate(engine, client, admin_token, admin_id) -> None:
    print("\n===== P-9 人工 invalidate：assembled→invalidated；active 拒；viewer 403 =====")
    await _seed_agent(engine, "pul-p9a")
    a = await _seed_assembled(engine, "pul-p9a", '{"q": "inv-a"}')
    s, b = await _invalidate(client, a["link_id"], admin_token)
    lk = await _link_by_id(engine, a["link_id"])
    check("P-9 assembled → invalidated(manual_invalidate, invalidated_by=admin)",
          s == 200 and b["offline_status"] == "invalidated"
          and lk.invalidate_reason == "manual_invalidate" and lk.invalidated_by == admin_id,
          f"{s} {b} reason={lk.invalidate_reason} by={lk.invalidated_by}")
    # conv(action=invalidate) 落库
    async with AsyncSession(engine) as s2:
        actions = list((await s2.scalars(
            select(ConversionRecord.action).where(ConversionRecord.link_id == a["link_id"])
        )).all())
    check("P-9 conv 记 assemble+invalidate",
          "invalidate" in actions and "assemble" in actions, f"actions={actions}")
    await _seed_agent(engine, "pul-p9act")
    act = await _seed_assembled(engine, "pul-p9act", '{"q": "inv-active"}')
    assert (await _ack(client, act["payload_id"], "active", case_id="c-p9"))[0] == 200
    s2, b2 = await _invalidate(client, act["link_id"], admin_token)
    check("P-9 active 行 invalidate → ERR_CLUSTER_0003(400)",
          s2 == 400 and b2["code"] == "ERR_CLUSTER_0003", f"{s2} {b2}")
    viewer_id = await _ensure_user(engine, VIEWER, "viewer")
    viewer_token = create_access_token(_app_settings(), viewer_id, "viewer")
    await _seed_agent(engine, "pul-p9v")
    v = await _seed_assembled(engine, "pul-p9v", '{"q": "inv-viewer"}')
    s3, b3 = await _invalidate(client, v["link_id"], viewer_token)
    check("P-9 viewer → ERR_AUTH_0002(403)",
          s3 == 403 and b3["code"] == "ERR_AUTH_0002", f"{s3} {b3}")


async def p10_requeue_e22(engine, client, admin_token) -> None:
    print("\n===== P-10 requeue 复位 + E-22（since 旧水位重拉可见） =====")
    await _seed_agent(engine, "pul-p10", version=1)
    mk = await _seed_assembled(engine, "pul-p10", '{"q": "q"}')
    pid = mk["payload_id"]
    await _backdate(engine, mk["link_id"], minutes=10)
    t0 = (await _link_by_id(engine, mk["link_id"])).assembled_ts
    s0, b0 = await _pull(client, "pul-p10", since_ts=iso_utc(t0))
    check("P-10 首次拉取命中（旧水位）", len(b0["payloads"]) == 1, f"got={len(b0['payloads'])}")
    # 模拟 content gap 结构自检驳回
    assert (await _ack(client, pid, "invalidated", reason="online_content_gap"))[0] == 200
    # 内容缺愈：词表 v1→v2（补内容）→ requeue 以新词表重填
    await _bump_wordlist(engine, "pul-p10", words=WORDS_V2, version=2)
    s, b = await _requeue(client, mk["link_id"], admin_token)
    lk = await _link_by_id(engine, mk["link_id"])
    env = await _link_env(engine, mk["link_id"])
    check("P-10 requeue 复位：payload_id 复用 + 新词表重填 + assembled_ts 刷新 + 清标注",
          s == 200 and b["offline_status"] == "assembled"
          and lk.offline_status == "assembled" and lk.verify_status == "pending"
          and lk.payload_id == pid and env["payload_id"] == pid
          and env["no_fallback_config"]["wordlist_version"] == 2
          and env["no_fallback_config"]["words"] == WORDS_V2
          and lk.assembled_ts > t0
          and lk.invalidate_reason is None and lk.invalidated_by is None,
          f"{s} wlv={env['no_fallback_config']['wordlist_version']}"
          f" ts_refresh={lk.assembled_ts > t0}")
    s2, b2 = await _pull(client, "pul-p10", since_ts=iso_utc(t0))
    check("P-10 E-22：since 旧水位重拉可见（重推案重入增量范围）",
          len(b2["payloads"]) == 1 and b2["payloads"][0]["payload_id"] == pid
          and b2["payloads"][0]["no_fallback_config"]["wordlist_version"] == 2,
          f"got={len(b2['payloads'])}")
    # conv(action=requeue) 落库
    async with AsyncSession(engine) as s3:
        actions = list((await s3.scalars(
            select(ConversionRecord.action).where(ConversionRecord.link_id == mk["link_id"])
        )).all())
    check("P-10 conv 记 assemble+requeue",
          actions.count("assemble") == 1 and actions.count("requeue") == 1, f"actions={actions}")


async def p11_requeue_guards(engine, client, admin_token) -> None:
    print("\n===== P-11 requeue 守卫：fixed cluster 拒 + 防抖 <5min 拒 =====")
    await _seed_agent(engine, "pul-p11a")
    a = await _seed_assembled(engine, "pul-p11a", '{"q": "fixed"}', status="fixed")
    await _backdate(engine, a["link_id"], minutes=10)
    assert (await _ack(client, a["payload_id"], "invalidated",
                       reason="online_content_gap"))[0] == 200
    s, b = await _requeue(client, a["link_id"], admin_token)
    check("P-11 fixed cluster → ERR_CLUSTER_0003（closed → superseded+reopen）",
          s == 400 and b["code"] == "ERR_CLUSTER_0003" and "superseded" in b["message"],
          f"{s} {b}")
    await _seed_agent(engine, "pul-p11b")
    fresh = await _seed_assembled(engine, "pul-p11b", '{"q": "debounce"}')
    # 不回拨：assembled_ts = 刚组装（<5min）→ requeue 直接防抖拒（无需先 requeue 循环）
    assert (await _ack(client, fresh["payload_id"], "invalidated",
                       reason="online_content_gap"))[0] == 200
    s2, b2 = await _requeue(client, fresh["link_id"], admin_token)
    check("P-11 防抖 <5min → ERR_CLUSTER_0003（含防抖字面）",
          s2 == 400 and b2["code"] == "ERR_CLUSTER_0003" and "防抖" in b2["message"],
          f"{s2} {b2}")


async def p12_requeue_batch(engine, client, admin_token) -> None:
    print("\n===== P-12 requeue-batch：content_gap×2 requeued + cap_gap 滤外"
          " + fresh 防抖 skip =====")
    agent = "pul-p12"
    await _seed_agent(engine, agent)
    ids_ok = []
    for i in range(2):
        mk = await _seed_assembled(engine, agent, '{"q": "ok-%d"}' % i)
        await _backdate(engine, mk["link_id"], minutes=10)
        assert (await _ack(client, mk["payload_id"], "invalidated",
                           reason="online_content_gap"))[0] == 200
        ids_ok.append(mk["link_id"])
    fresh = await _seed_assembled(engine, agent, '{"q": "fresh"}')  # 不回拨：ts 刚组装
    assert (await _ack(client, fresh["payload_id"], "invalidated",
                       reason="online_content_gap"))[0] == 200
    cap = await _seed_assembled(engine, agent, '{"q": "cap"}')
    await _backdate(engine, cap["link_id"], minutes=10)
    assert (await _ack(client, cap["payload_id"], "invalidated",
                       reason="offline_cap_gap"))[0] == 200
    s, b = await _batch(client, admin_token, agent=agent)
    req_ids = sorted(x["link_id"] for x in b["requeued"])
    check("P-12 批量 2 行 requeued + cap_gap 过滤在外 + fresh 行防抖 skipped",
          s == 200 and req_ids == sorted(ids_ok)
          and cap["link_id"] not in req_ids
          and len(b["skipped"]) == 1 and b["skipped"][0]["link_id"] == fresh["link_id"]
          and "防抖" in b["skipped"][0]["reason"],
          f"requeued={req_ids} expect={sorted(ids_ok)} "
          f"skipped={[(x['link_id'], x['reason']) for x in b['skipped']]}")
    for lid in ids_ok:
        lk = await _link_by_id(engine, lid)
        if lk.offline_status != "assembled":
            check("P-12 requeue 行复位 assembled", False, f"link {lid} off={lk.offline_status}")
            return
    async with AsyncSession(engine) as s2:
        agg = (await s2.scalars(
            select(ConversionRecord).where(ConversionRecord.cluster_id.is_(None),
                                           ConversionRecord.action == "requeue",
                                           ConversionRecord.link_id.is_(None))
        )).first()
    detail = json.loads(agg.detail) if agg else {}
    check("P-12 批量 conv 汇总落库（filter/计数）",
          agg is not None and detail.get("requeued") == 2 and detail.get("skipped") == 1
          and detail.get("filter", {}).get("agent") == agent,
          f"detail={agg.detail if agg else None}")


async def p13_double_ack_e15(engine, client) -> None:
    print("\n===== P-13 E-15：同 payload 连续双 ack（active）均 200、终态恰一次 =====")
    await _seed_agent(engine, "pul-p13")
    mk = await _seed_assembled(engine, "pul-p13", '{"q": "q"}')
    pid = mk["payload_id"]
    s1, b1 = await _ack(client, pid, "active", case_id="case-p13")
    s2, b2 = await _ack(client, pid, "active", case_id="case-p13")  # 重放 → noop 200
    lk = await _link_by_payload(engine, pid)
    check("P-13 双 active ack 均 200（首 apply / 次幂等）+ 终态 active",
          s1 == 200 and b1["offline_status"] == "active"
          and s2 == 200 and b2["offline_status"] == "active"
          and lk.offline_status == "active" and lk.case_id == "case-p13",
          f"{s1}/{s2} off={lk.offline_status}")


_settings_cache = {}


def _app_settings() -> Settings:
    if "s" not in _settings_cache:
        _settings_cache["s"] = Settings(app_env="test", resource_env="dev",
                                        jwt_secret=_JWT, evaluator_service_secret=_SECRET)
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
        admin_id = await _ensure_user(engine, ADMIN, "admin")  # cleanup 后重建（防 401）
        admin_token = create_access_token(_app_settings(), admin_id, "admin")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://probe") as client:
            await p1_empty(engine, client)
            await p2_pull_fields(engine, client)
            await p3_pagination(engine, client)
            await p4_ack_draft_idempotent(engine, client)
            await p5_ack_active_requires_case_id(engine, client)
            await p6_ack_invalidated_replay(engine, client)
            await p7_r2_exception(engine, client)
            await p8_unknown_payload(engine, client)
            await p9_admin_invalidate(engine, client, admin_token, admin_id)
            await p10_requeue_e22(engine, client, admin_token)
            await p11_requeue_guards(engine, client, admin_token)
            await p12_requeue_batch(engine, client, admin_token)
            await p13_double_ack_e15(engine, client)
    finally:
        await _cleanup(engine)
        await engine.dispose()
    print("\n===== pull_probe 结果 =====")
    if FAILURES:
        print(f"FAIL: {len(FAILURES)} 项失败 → {FAILURES}")
        sys.exit(1)
    print("全绿：P2-3 pull-API/ack/invalidate/requeue 13 场景通过")


if __name__ == "__main__":
    asyncio.run(main())
