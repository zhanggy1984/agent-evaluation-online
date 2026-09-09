"""D19 统一 case payload 信封组装（detail §6.3 / §7.1，P2-2 / T-3.2）。

- `build_envelope` 纯函数：cluster 行 → 信封 dict（键序对齐 §7.1 sample）。供
  assemble_job 组装新发（payload_id=uuid4()，幂等键）与 **P2-3 requeue 复用旧
  payload_id 重填**（content_gap 补齐后以现词表重推，§7.4：重填 payload_json 不改
  payload_id）。
- `assemble_cluster` 单簇组装编排：resolve wordlist → build_envelope → 写
  error_case_link（assembled+pending）+ conversion_record(action=assemble) 一步
  事务。uk_link_current/uk_link_payload 冲突（双 worker 竞态）上抛 IntegrityError
  由调用方 savepoint 吸收（E-12 先例）。
- 组装即取即时值、永不回写：versions.fix_version = cluster.fix_version（claim 前
  cluster 无 fix_version → null，回查锚定 cluster.fix_version，§6.3/§7.6）。
- input_truncated **不进信封 JSON**，随 error_case_link.input_truncated 透传
  （§7.1 行 + sample 证实）；evidence.output 恒 null（body 采集默认关，§7.1）。
"""
import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.converter.no_fallback_cfg import resolve_fallback_wordlist
from app.models.error_flow import ConversionRecord, ErrorCaseLink

SCHEMA_VERSION = "1.0"
CASE_TYPE = "regression_error"
NO_FALLBACK_RULE = "wordlist"


def parse_snapshot_input(snapshot: str | None):
    """error_cluster.input_snapshot 文本 → evidence.input。

    快照源 = 判定态 input_snapshot_clean（dict/list 原始 input 存**原序** JSON 文本，
    str 原始 input 存明文）→ json.loads 成功嵌 parse 后值（对象/数组复现 sample
    形态），失败（明文 str）嵌原文。空/None 防御返回 None。
    """
    if not snapshot:
        return None
    try:
        return json.loads(snapshot)
    except (ValueError, TypeError):
        return snapshot


def build_envelope(
    *, cluster, words: list[str], wordlist_version: int, payload_id: str | None = None
) -> dict:
    """cluster（ORM 行或 SimpleNamespace，须有 agent/interface/first_trace_id/id/
    generation/trigger_version/fix_version/input_snapshot）→ D19 信封 dict。

    键序对齐 §7.1 sample；assert.config_ref.wordlist_version ===
    no_fallback_config.wordlist_version（同刻固化同源，单一版本源）。
    payload_id：缺省新发 uuid4（组装幂等键）；requeue 重填传旧 payload_id 复用
    （§7.4 锚点保护：复位不改 payload_id，offline upsert 幂等）。
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "case_type": CASE_TYPE,
        "payload_id": payload_id or str(uuid.uuid4()),
        "source": {
            "agent": cluster.agent,
            "interface": cluster.interface,
            "trace_id": cluster.first_trace_id,
            "cluster_id": cluster.id,
            "generation": cluster.generation,
        },
        "versions": {
            "trigger_version": cluster.trigger_version,
            "fix_version": cluster.fix_version,  # 组装即时值（claim 前恒 null，不回写）
        },
        "evidence": {
            "input": parse_snapshot_input(cluster.input_snapshot),
            "output": None,  # body 采集默认关恒 null（§7.1 可空不得驳回）
            "session_snapshot": None,  # 二期恒 null
            "retrieve_hit": None,  # 二期恒 null
        },
        "assert": {
            "no_fallback": {
                "rule": NO_FALLBACK_RULE,
                "config_ref": {"wordlist_version": wordlist_version},
            }
        },
        "no_fallback_config": {
            "words": list(words),
            "wordlist_version": wordlist_version,
        },
    }


async def assemble_cluster(session: AsyncSession, cluster) -> bool:
    """单簇组装：信封 + link（assembled+pending）+ conv(action=assemble) 一步落库。

    快照缺 input 实文（input_snapshot 空）→ 只计数不组装返回 False（E-13，§6.3
    step1；待同键新现补齐快照后由 assemble_job 下轮扫到）。IntegrityError（并发
    双 worker 同簇已建现行 link / payload_id 撞唯一）上抛，调用方 savepoint 吸收。
    返回是否建了 link。
    """
    if not cluster.input_snapshot:
        return False
    words, wordlist_version = await resolve_fallback_wordlist(
        session, agent_name=cluster.agent
    )
    envelope = build_envelope(
        cluster=cluster, words=words, wordlist_version=wordlist_version
    )
    payload_id = envelope["payload_id"]
    link = ErrorCaseLink(
        cluster_id=cluster.id,
        payload_id=payload_id,
        case_type=CASE_TYPE,
        source_trace_id=cluster.first_trace_id,
        trigger_version=cluster.trigger_version,  # 仅溯源（自 cluster 复制）
        fix_version=cluster.fix_version,
        input_truncated=cluster.input_truncated,  # 随 link 透传（§7.1）
        payload_json=json.dumps(envelope, ensure_ascii=False),
        # offline_status=assembled / verify_status=pending 走列 server_default
    )
    session.add(link)
    await session.flush()  # 取 link.id 供 conv 关联（未 flush 前 id 为空）
    session.add(
        ConversionRecord(
            cluster_id=cluster.id,
            link_id=link.id,
            action="assemble",
            detail=(
                f"组装 D19 信封 payload_id={payload_id}"
                f"（wordlist_v={wordlist_version} words={len(words)}）"
            ),
            actor_user_id=None,  # 系统动作记 NULL
        )
    )
    return True
