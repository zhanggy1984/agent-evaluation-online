"""P2-2 组装 DB 壳集成探针（detail §6.3 / §7.1，T-3.2）。容器内 `docker exec obs-backend` 运行：

    docker exec obs-backend python /app/tests/integration/assemble_probe.py

前置：obs-backend 已 up（同后端 env：DB_HOST=mysql 容器内 alias）；探针自建 async engine。

覆盖 converter/assemble「DB 壳留集成探针」先例下单测无法覆盖的实库语义（多行 select /
uk_link_current 生成列唯一 / dict_config 真读 / JSON 列往返 / 列 server_default）：
  A-1 首现 open+快照+词表配置 → 组装恰 1 link（assembled+pending、payload_id uuid、
      source_trace_id/trigger_version/fix_version/input_truncated 复制）+ 1 conv(action=assemble)；
      envelope 逐字段（source/versions/evidence.input 还原 dict/assert 与 no_fallback_config
      wordlist_version 同源一致）+ payload_json 中文 ensure_ascii 可回读；
  A-2 窗口抑制：已有 pending link 的 open cluster 不出现在扫描候选（§6.3 不重复组装）；
  A-3 快照缺 input 实文（NULL）→ 只计数不组装：无 link、无 conv（E-13，§6.3 step1）；
  A-4 fallback_utterance 空表（seed 默认形态）→ link 照建、envelope words==[]（fail-closed）；
  A-5 uk_link_current 在库真在：同 cluster 二次组装 → IntegrityError（E-12 双实例吸收面）；
  A-6 cluster.fix_version 预置 → envelope versions.fix_version 带出组装即时值；
  A-7 非 open（fixed）cluster 不进扫描候选。

隔离：探针 agent 前缀 asm-（≤64 字符），开头按 asm-% 清理残留（agent/dict_config/cluster/
link/conv 自 cluster 关联），结尾再清。不触发 run_assemble 全局扫（防把库内真实 open
cluster 无差别组装出 link）——扫描候选语义由 A-2/A-7 经 _scan_candidates 判据核验。退出码全绿 0。
"""
import asyncio
import json
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/app")

from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.converter.envelope import assemble_cluster  # noqa: E402
from app.converter.no_fallback_cfg import resolve_fallback_wordlist  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.models.agent import Agent  # noqa: E402
from app.models.config import DictConfig  # noqa: E402
from app.models.error_flow import ConversionRecord, ErrorCaseLink, ErrorCluster  # noqa: E402
from app.worker.assemble_job import _scan_candidates  # noqa: E402

FAILURES: list[str] = []
IFACE = "POST /api/probe/{id}"
H1 = "a" * 64  # 固定 64-char 伪 hash（探针隔离，仅要求列宽与等值语义）
NOW = datetime.now(timezone.utc).replace(tzinfo=None)
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
DICT_KEY = "fallback_utterance"


def check(name: str, ok: bool, detail: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    if not ok:
        FAILURES.append(name)


async def _reset(engine) -> None:
    """清 asm-% 残留：conv→link（自 cluster 关联）→cluster→dict_config→agent（自关联）。"""
    async with AsyncSession(engine) as s:
        sub = select(ErrorCluster.id).where(ErrorCluster.agent.like("asm-%"))
        await s.execute(delete(ConversionRecord).where(ConversionRecord.cluster_id.in_(sub)))
        await s.execute(delete(ErrorCaseLink).where(ErrorCaseLink.cluster_id.in_(sub)))
        await s.execute(delete(ErrorCluster).where(ErrorCluster.agent.like("asm-%")))
        ag = select(Agent.id).where(Agent.name.like("asm-%"))
        await s.execute(delete(DictConfig).where(DictConfig.agent_id.in_(ag)))
        await s.execute(delete(Agent).where(Agent.name.like("asm-%")))
        await s.commit()


async def _seed_agent(engine, name: str, *, words: list | None, version: int = 7) -> int:
    """落 agent 行 + per-agent fallback_utterance 配置 → 返回 agent id。"""
    async with AsyncSession(engine) as s:
        agent = Agent(name=name, display_name=name, base_url=None, enable=1,
                      route_source="auto_register", backflow_allow=1)
        s.add(agent)
        await s.flush()
        if words is not None:
            s.add(DictConfig(agent_id=agent.id, config_key=DICT_KEY,
                             config_value=words, version=version, updated_by="probe"))
        agent_id = agent.id  # flush 后已回填；commit 后过期，先取值再提交
        await s.commit()
        return agent_id


async def _seed_cluster(engine, agent: str, *, snapshot, status="open",
                        fix_version=None, truncated=0) -> int:
    """落 open cluster（首现代表字段形态）→ 返回 cluster id。"""
    async with AsyncSession(engine) as s:
        row = ErrorCluster(
            agent=agent, interface=IFACE, layer="L1", error_type="llm_timeout",
            input_hash=H1, input_snapshot=snapshot, input_truncated=truncated,
            error_msg="provider timeout", first_trace_id=f"asm-{agent}-1",
            trigger_version="2026.09.09-r1", fix_version=fix_version,
            first_ts=NOW, latest_ts=NOW, count=1, generation=1, status=status,
        )
        s.add(row)
        await s.flush()
        cluster_id = row.id  # commit 后过期，先取值再提交
        await s.commit()
        return cluster_id


async def _links(engine, cluster_id: int) -> list:
    async with AsyncSession(engine) as s:
        return list((await s.scalars(
            select(ErrorCaseLink).where(ErrorCaseLink.cluster_id == cluster_id)
        )).all())


async def _convs(engine, cluster_id: int) -> list:
    async with AsyncSession(engine) as s:
        return list((await s.scalars(
            select(ConversionRecord).where(ConversionRecord.cluster_id == cluster_id)
        )).all())


async def _scan_ids(engine) -> set[int]:
    async with AsyncSession(engine) as s:
        return {c.id for c in await _scan_candidates(s, batch=200)}


async def a1_assemble(engine) -> None:
    print("\n===== A-1 首现组装：link + conv + envelope 逐字段 =====")
    agent = "asm-a1"
    await _seed_agent(engine, agent,
                      words=["抱歉，暂时无法回答", "系统繁忙，请稍后再试"], version=7)
    snap = json.dumps({"question": "帮我查一下XX政策"}, ensure_ascii=False)
    cid = await _seed_cluster(engine, agent, snapshot=snap)
    async with AsyncSession(engine) as s:
        cluster = (await s.scalars(
            select(ErrorCluster).where(ErrorCluster.id == cid))).one()
        ok = await assemble_cluster(s, cluster)
        await s.commit()
    check("A-1 组装执行（快照非空）", bool(ok), f"ok={ok}")
    links = await _links(engine, cid)
    convs = await _convs(engine, cid)
    check("A-1 恰 1 link + 1 conv(action=assemble)",
          len(links) == 1 and len(convs) == 1
          and convs[0].action == "assemble" and convs[0].cluster_id == cid
          and convs[0].link_id == links[0].id and convs[0].actor_user_id is None,
          f"links={len(links)} convs={len(convs)} conv.action={convs[0].action if convs else None}")
    if links:
        lk = links[0]
        check("A-1 link 状态字段（assembled/pending）+ 溯源/版本/截断复制",
              lk.offline_status == "assembled" and lk.verify_status == "pending"
              and lk.case_type == "regression_error"
              and lk.source_trace_id == f"asm-{agent}-1"
              and lk.trigger_version == "2026.09.09-r1"
              and lk.fix_version is None and lk.input_truncated == 0
              and UUID_RE.match(lk.payload_id),
              f"off={lk.offline_status} ver={lk.verify_status} src={lk.source_trace_id}")
        env = json.loads(lk.payload_json)
        check("A-1 envelope 逐字段（source/versions/evidence/assert/词表同源）",
              env["schema_version"] == "1.0" and env["case_type"] == "regression_error"
              and env["payload_id"] == lk.payload_id
              and env["source"] == {"agent": agent, "interface": IFACE,
                                    "trace_id": f"asm-{agent}-1",
                                    "cluster_id": cid, "generation": 1}
              and env["versions"] == {"trigger_version": "2026.09.09-r1", "fix_version": None}
              and env["evidence"]["input"] == {"question": "帮我查一下XX政策"}
              and env["evidence"]["output"] is None
              and env["assert"]["no_fallback"]["rule"] == "wordlist"
              and env["assert"]["no_fallback"]["config_ref"]["wordlist_version"]
              == env["no_fallback_config"]["wordlist_version"]
              and env["no_fallback_config"]["words"]
              == ["抱歉，暂时无法回答", "系统繁忙，请稍后再试"],
              f"payload_id_same={env['payload_id'] == lk.payload_id} "
              f"wlv={env['no_fallback_config']['wordlist_version']}")
        check("A-1 中文直存可回读", "帮我查一下XX政策" in lk.payload_json, "ensure_ascii=False")


async def a2_window_suppression(engine) -> None:
    print("\n===== A-2 窗口抑制：已有 pending link 不进扫描候选 =====")
    agent = "asm-a2"
    await _seed_agent(engine, agent, words=["抱歉，暂时无法回答"], version=1)
    cid = await _seed_cluster(engine, agent, snapshot='{"question": "q"}')
    async with AsyncSession(engine) as s:
        cluster = (await s.scalars(
            select(ErrorCluster).where(ErrorCluster.id == cid))).one()
        await assemble_cluster(s, cluster)  # 建现行 link（pending）
        await s.commit()
    check("A-2 已建 link 后不在扫描候选（不重复组装）",
          cid not in await _scan_ids(engine),
          f"cid={cid} 在候选中" if cid in await _scan_ids(engine) else "cid 已排除")
    check("A-2 库内仍恰 1 link", len(await _links(engine, cid)) == 1, "")


async def a3_snapshot_missing(engine) -> None:
    print("\n===== A-3 快照缺 → 只计数不组装（E-13） =====")
    agent = "asm-a3"
    await _seed_agent(engine, agent, words=["抱歉，暂时无法回答"], version=1)
    cid = await _seed_cluster(engine, agent, snapshot=None)
    async with AsyncSession(engine) as s:
        cluster = (await s.scalars(
            select(ErrorCluster).where(ErrorCluster.id == cid))).one()
        ok = await assemble_cluster(s, cluster)
        await s.commit()
    check("A-3 快照 NULL 不组装",
          not ok and len(await _links(engine, cid)) == 0 and len(await _convs(engine, cid)) == 0,
          f"ok={ok} links={len(await _links(engine, cid))}")


async def a4_empty_wordlist(engine) -> None:
    print("\n===== A-4 空词表 → link 照建 + words==[]（fail-closed） =====")
    agent = "asm-a4"
    await _seed_agent(engine, agent, words=[], version=1)  # seed 默认形态
    cid = await _seed_cluster(engine, agent, snapshot='{"question": "q"}')
    async with AsyncSession(engine) as s:
        cluster = (await s.scalars(
            select(ErrorCluster).where(ErrorCluster.id == cid))).one()
        await assemble_cluster(s, cluster)
        await s.commit()
    links = await _links(engine, cid)
    if links:
        env = json.loads(links[0].payload_json)
        check("A-4 空词表信封照建（words==[] + wordlist_version 一致）",
              env["no_fallback_config"] == {"words": [], "wordlist_version": 1}
              and env["assert"]["no_fallback"]["config_ref"]["wordlist_version"] == 1,
              f"nf={env['no_fallback_config']}")


async def a5_unique_link(engine) -> None:
    print("\n===== A-5 uk_link_current 在库（同簇二次组装 → IntegrityError） =====")
    agent = "asm-a5"
    await _seed_agent(engine, agent, words=["抱歉，暂时无法回答"], version=1)
    cid = await _seed_cluster(engine, agent, snapshot='{"question": "q"}')
    async with AsyncSession(engine) as s:
        cluster = (await s.scalars(
            select(ErrorCluster).where(ErrorCluster.id == cid))).one()
        await assemble_cluster(s, cluster)
        await s.commit()
    got_ie = False
    async with AsyncSession(engine) as s:
        cluster = (await s.scalars(
            select(ErrorCluster).where(ErrorCluster.id == cid))).one()
        try:
            await assemble_cluster(s, cluster)  # 现行 pending 占位 → uk_link_current
            await s.commit()
        except IntegrityError:
            got_ie = True
            await s.rollback()
    check("A-5 二次组装被 uk_link_current 拒绝（IntegrityError）",
          got_ie and len(await _links(engine, cid)) == 1
          and len(await _convs(engine, cid)) == 1,
          f"got_integrity_error={got_ie}")


async def a6_fix_version_taken(engine) -> None:
    print("\n===== A-6 fix_version 组装即时值带出 =====")
    agent = "asm-a6"
    await _seed_agent(engine, agent, words=["x"], version=2)
    cid = await _seed_cluster(engine, agent, snapshot='{"question": "q"}',
                              fix_version="2026.09.05-r2")
    async with AsyncSession(engine) as s:
        cluster = (await s.scalars(
            select(ErrorCluster).where(ErrorCluster.id == cid))).one()
        await assemble_cluster(s, cluster)
        await s.commit()
    links = await _links(engine, cid)
    if links:
        env = json.loads(links[0].payload_json)
        check("A-6 envelope fix_version = 组装即时值（link 列同步）",
              env["versions"]["fix_version"] == "2026.09.05-r2"
              and links[0].fix_version == "2026.09.05-r2",
              f"env={env['versions']['fix_version']}")


async def a7_non_open_excluded(engine) -> None:
    print("\n===== A-7 非 open（fixed）cluster 不进扫描候选 =====")
    agent = "asm-a7"
    await _seed_agent(engine, agent, words=["x"], version=1)
    cid = await _seed_cluster(engine, agent, snapshot='{"question": "q"}', status="fixed")
    check("A-7 fixed cluster 不在候选（不组装）",
          cid not in await _scan_ids(engine),
          f"cid={cid} 在候选中" if cid in await _scan_ids(engine) else "cid 已排除")


async def wl_read(engine) -> None:
    print("\n===== W-1 resolve_fallback_wordlist 真库读三态 =====")
    agent = "asm-w1"
    await _seed_agent(engine, agent, words=["抱歉，暂时无法回答"], version=3)
    async with AsyncSession(engine) as s:
        got = await resolve_fallback_wordlist(s, agent_name=agent)
        check("W-1 命中：words + version", got == (["抱歉，暂时无法回答"], 3), f"got={got}")
    async with AsyncSession(engine) as s:
        got = await resolve_fallback_wordlist(s, agent_name="asm-ghost")
        check("W-1 agent 缺：空表 fail-closed", got == ([], 0), f"got={got}")


async def main() -> None:
    settings = Settings()
    engine = create_async_engine(settings.sqlalchemy_url)
    try:
        await _reset(engine)  # 幂等：清 asm-% 残留（防重跑累积干扰断言）
        await a1_assemble(engine)
        await a2_window_suppression(engine)
        await a3_snapshot_missing(engine)
        await a4_empty_wordlist(engine)
        await a5_unique_link(engine)
        await a6_fix_version_taken(engine)
        await a7_non_open_excluded(engine)
        await wl_read(engine)
    finally:
        await _reset(engine)
        await engine.dispose()
    print("\n===== assemble_probe 结果 =====")
    if FAILURES:
        print(f"FAIL: {len(FAILURES)} 项失败 → {FAILURES}")
        sys.exit(1)
    print("全绿：P2-2 组装 DB 壳 8 场景通过")


if __name__ == "__main__":
    asyncio.run(main())
