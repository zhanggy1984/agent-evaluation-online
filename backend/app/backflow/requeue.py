"""backflow 重推（§7.4 R-7 可愈性标注 + 自动重推出口）。

- `requeue_guard_errors`：纯守卫函数（无 IO，单测直打），自动出口与人工入口共用同一套规则。
- `requeue_counts`：成批取各 link **历史** requeue 次数 → {link_id: count}（读面用）。
  口径 = 不含本次（只数已落库的 conversion_record(action=requeue) 行）。
- `auto_requeue_stuck`：把卡在 invalidated(online_content_gap) 的 link 复位重推（批 37）。

⚠️ 批 35-B 曾把人工失效 / 重推 / 复位的**写面整体撤除**（`requeue_link` / `requeue_batch` /
`invalidate_link` 及其 9 个端点 + UI）。**批 37 部分回滚**：用户拍板「出口要自动、不要按钮」
⇒ 只恢复**自动**复位（`auto_requeue_stuck`，由 worker 周期驱动），**HTTP 写端点仍不恢复**。

⚠️ 为什么必须有这个自动出口（35-B 的登记是错的）：offline 契约**早已定义**了这条恢复路径 ——
离线详设 §5.5 可愈性（`content_gap`「admin 补齐后 requeue 可愈」/ `empty_words` 同 /
`version_drift`「requeue **不愈**」）、§6.5 重处理谓词（`online_content_gap` 行按
**assembled_ts 被刷新**判定「内容已刷新」）、§7.4 防抖与上限。35-B 只读了 online 这一侧
就把「6 条无自动出口」签成**判不做**，理由是「要定的是新的产品规则」——**前提是假的**：
规则写在另一侧的契约里。本模块即那条被砍断的路径的自动化。
"""

import json
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.converter.envelope import build_envelope
from app.converter.no_fallback_cfg import resolve_fallback_wordlist
from app.core.log import get_logger
from app.models.error_flow import ConversionRecord, ErrorCaseLink, ErrorCluster

logger = get_logger("worker.requeue")

REQUEUE_DEBOUNCE_MINUTES = 5          # §7.4：同一 link 重推间隔 ≥5min（锚 = assembled_ts）
REQUEUE_ALLOWED_CLUSTER = ("open", "claim", "needs_review")   # R-24：fixed/inactive closed 禁
MANUAL_INVALIDATE_REASON = "manual_invalidate"
# cap_gap 的识别码（与 ack.py 的 R2 例外同源取值）。消费点：requeue 守卫据此拒绝重推
# （恢复面在离线侧）；自动出口的 where 本来就把候选限在 online_content_gap。
CAP_GAP_REASON = "offline_cap_gap"

# 自动重推上限（批 37 配置化）：dict_config 全局键，seed 默认 2。
# ⚠️ 与 `SUSPECT_REQUEUE_THRESHOLD` **同值不同物**：那个是「前端把 ≥N 次仍被驳回的 link
# 标成『疑似不可自愈』」的展示阈值，本键是**后端真的停手**的判据。改其一须考虑另一。
# 每轮扫描都过 `get_global_int`（**无本模块快照**），但**该函数自带 60s 进程内缓存**
# ⇒ admin 改完经由 `invalidate_cache()` 即时生效，直接改库则最迟 60s 生效。
# ⚠️ 别在注释里写成「每次现读、无缓存」——真实行为是「现读 + 60s 缓存」（见 dict_config.py）。
AUTO_REQUEUE_MAX_KEY = "auto_requeue_max_default"

# 单批候选 link 数（同 assemble 粒度）
REQUEUE_BATCH = 200

# R-7 可愈性标注（换判据 = 行为数据）：已重推过 ≥该次数仍 invalidated 回来 = 疑似不可自愈
# （如版本不识别 / 配置长期未补齐），前端据此转强确认（二次确认）。该值系拍定、无数据支撑，
# 上线后按真实 conversion_record 分布调。
# ⚠️ 批 37 起：本常量的「唯一行为源 = 前端」**已不成立** —— 后端 `auto_requeue_stuck`
# 用 `AUTO_REQUEUE_MAX_KEY` 真的停手。前端仍是展示侧的唯一来源。
SUSPECT_REQUEUE_THRESHOLD = 2


# ---------- 纯守卫（无 IO，单测直打；自动出口与人工入口共用） ----------


def requeue_guard_errors(link, cluster, *, now: datetime) -> str | None:
    """§7.4 R-24 守卫链：通过返回 None，否则返回可读原因（自动出口据此跳过该 link）。"""
    if link.offline_status != "invalidated":
        return f"仅 invalidated 可重推（当前 offline_status={link.offline_status}）"
    if link.invalidate_reason == CAP_GAP_REASON:
        # cap_gap 的恢复面在**离线侧**（补登记 agent/interface），online 补不了 ⇒ 重推没有
        # 有效作用，只会造成三个真实损失：①**假动作**——离线端拉到该 payload 后被重处理
        # 谓词跳过（`_needs_reprocess` 对 offline_cap_gap 只放 {none,pending}，该行已 acked）
        # ⇒ 记录里显示成功而实际零处理；②**载荷分叉**——重推会用现 cluster+现词表重渲染
        # payload_json 并刷新 assembled_ts，而离线 inbox 里仍是旧 envelope_json；
        # ③**污染 R-7 可愈性计数**——把「从未被受理」记成「重推多次仍不行」。
        # 正确路径 = 离线「等待接入」探测态每小时自愈（离线详设 §5.8）。
        return (
            "offline_cap_gap 不可重推：恢复面在离线侧（补登记 agent/interface），"
            "online 补不了登记；重推会被离线重处理谓词跳过（假动作）并污染可愈性计数。"
            "正确路径 = 离线「等待接入」探测态每小时自愈（§5.8）"
        )
    if link.verify_status != "pending":
        return (
            f"verify 兜底：仅 verify_status=pending 的 invalidated link 走此路"
            f"（当前={link.verify_status}，已推进 passed/failed/superseded 需 superseded+reopen）"
        )
    if cluster is None:
        return "cluster 不存在（link.cluster_id 悬空）"
    if cluster.status not in REQUEUE_ALLOWED_CLUSTER:
        return (
            f"cluster 已 closed（status={cluster.status}）禁重推——需 superseded+reopen"
            f" 重建新 link/新 payload_id（§7.4，防对已收敛证据翻案）"
        )
    idle = now - link.assembled_ts
    if idle < timedelta(minutes=REQUEUE_DEBOUNCE_MINUTES):
        return (
            f"防抖：距上次组装/重推 <{REQUEUE_DEBOUNCE_MINUTES}min"
            f"（{idle.total_seconds():.0f}s，锚 = assembled_ts，§7.4）"
        )
    return None


# ---------- requeue 计数（R-7 可愈性标注的数据源：行为数据） ----------


async def requeue_counts(session: AsyncSession, link_ids: list[int]) -> dict[int, int]:
    """批量取各 link **历史** requeue 次数 → {link_id: count}（读面用）。

    成批一次 GROUP BY：读面一屏多个 link，逐 link 单查 COUNT 就是 N+1。
    口径 = 不含本次（只数已落库的 conversion_record(action=requeue) 行），故正在 add
    而未落库的那条不计入。返回只含命中 link，未命中者由调用方取 0。
    """
    if not link_ids:  # 空入参不发查询
        return {}
    rows = (await session.execute(
        select(ConversionRecord.link_id, func.count())
        .where(
            ConversionRecord.link_id.in_(link_ids),
            ConversionRecord.action == "requeue",
        )
        .group_by(ConversionRecord.link_id)
    )).all()
    return {link_id: int(cnt) for link_id, cnt in rows}


async def requeue_count(session: AsyncSession, link_id: int) -> int:
    """单点便捷：复用成批实现，口径同上 = 历史次数（不含本次）。"""
    return (await requeue_counts(session, [link_id])).get(link_id, 0)


# ---------- 自动重推出口（批 37；由 worker assemble_job 每 60s 内联调用） ----------


async def auto_requeue_stuck(
    session: AsyncSession, *, now: datetime, cap: int, batch: int = REQUEUE_BATCH
) -> int:
    """扫并复位卡在 invalidated(online_content_gap) 的 link → 返回本次复位条数。

    复位 = invalidated→assembled + **以现 cluster + 现词表重填 payload_json**（内容缺愈：
    这条路径能救的是「上游数据补齐后重算即可通过」的驳回，不是「重发旧载荷」）+
    刷新 assembled_ts=now（离线据此判定「内容已刷新」并重拉，§6.5），清
    invalidate_reason / invalidated_by；**复用 payload_id**（离线 upsert 幂等，§7.4）；
    cluster 锚点（fix_version/claim_k/TTL）与 link.verify_status 均**不动**（仍占现行位 §5.1）。

    不 commit —— 由调用方（assemble_job 每批一个事务）统一提交。
    `cap` 由调用方现读配置传入；已达上限的 link 只记 debug、不复位（R-7 转人工）。
    """
    cutoff = now - timedelta(minutes=REQUEUE_DEBOUNCE_MINUTES)
    rows = (await session.execute(
        select(ErrorCaseLink, ErrorCluster)
        .join(ErrorCluster, ErrorCluster.id == ErrorCaseLink.cluster_id)
        .where(
            ErrorCaseLink.offline_status == "invalidated",
            # 候选只收 online_content_gap —— offline_cap_gap 的恢复面在离线侧（见守卫注释）
            ErrorCaseLink.invalidate_reason == "online_content_gap",
            ErrorCaseLink.verify_status == "pending",
            ErrorCaseLink.assembled_ts <= cutoff,          # 防抖（锚 = assembled_ts）
            ErrorCluster.status.in_(REQUEUE_ALLOWED_CLUSTER),
        )
        .order_by(ErrorCaseLink.id)
        .limit(batch)
    )).all()
    if not rows:
        return 0
    counts = await requeue_counts(session, [link.id for link, _ in rows])
    done = 0
    for link, cluster in rows:
        link_id, payload_id, cluster_id = link.id, link.payload_id, cluster.id
        n = counts.get(link_id, 0)
        if n >= cap:
            # 已达上限：疑似不可自愈（如 version_drift，offline 契约 §5.5「requeue 不愈」）
            # ⇒ 停手转人工。停在 invalidated 不动，前端按 R-7 显示「需人工介入」。
            logger.debug("自动重推已达上限，转人工", extra={"link_id": link_id, "n": n, "cap": cap})
            continue
        skip = requeue_guard_errors(link, cluster, now=now)   # 守卫生效：跳过并留痕
        if skip:
            logger.debug("自动重推被守卫跳过", extra={"link_id": link_id, "why": skip})
            continue
        words, wordlist_version = await resolve_fallback_wordlist(
            session, agent_name=cluster.agent
        )
        envelope = build_envelope(
            cluster=cluster, words=words, wordlist_version=wordlist_version,
            payload_id=payload_id,   # 复用旧 payload_id（离线 upsert 幂等，§7.4）
        )
        result = await session.execute(
            update(ErrorCaseLink)
            .where(
                ErrorCaseLink.id == link_id,
                ErrorCaseLink.offline_status == "invalidated",
                ErrorCaseLink.verify_status == "pending",
                ErrorCaseLink.assembled_ts <= cutoff,
            )
            .values(
                offline_status="assembled",
                invalidate_reason=None,
                invalidated_by=None,
                payload_json=json.dumps(envelope, ensure_ascii=False),
                assembled_ts=now,
            )
        )
        if result.rowcount != 1:
            # 竞态：与 offline ack / 他 worker 交错（无 HTTP 层，跳过即可，不下结论）
            logger.debug("自动重推 CAS 落空，跳过", extra={"link_id": link_id})
            continue
        # detail 记下**当时生效的上限**：阈值可在 admin 页改，不记则事后无法复原判据
        session.add(ConversionRecord(
            cluster_id=cluster_id, link_id=link_id, action="requeue",
            detail=f"自动重推 #{n + 1}/上限 {cap}（内容以现 cluster+现词表重算）",
            actor_user_id=None,   # 系统动作记 NULL
        ))
        done += 1
    if done:
        logger.info("自动重推完成", extra={"requeued": done, "cap": cap})
    return done
