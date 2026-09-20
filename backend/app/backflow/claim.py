"""backflow 簇判定与自动收口（detail §7.6 / §8.4）。

⚠️ 批 35-B：**人工处置写面已整体撤除** —— claim / ignore / reopen / fixed-review /
needs-review-resolve 五个动作连端点在 `app/api/backflow.py` 一并删除，online 只读
（处置全部由 offline 定时拉取完成、回推结果）。故本模块只剩**系统侧**三个写面函数：

- `_mark_pending_links`：簇的现行 pending link 打终态（passed / failed / superseded），
  释放 cur_key（唯一键 uk_link_current 据此放宽，assemble_job 才装配得下一条）。
- `_apply_auto_fixed`：verify K 满 → cluster CAS open→fixed + 落 conv(action=auto_fixed)。
  批 35-A 准入已由 `claim` 改 `open`（无人认领 ⇒ claim 态不可达）。
- `_apply_verify_reopen`：回归 failed → **只记 conv(action=reopen)、不做 UPDATE**
  （活动态本就是 open，`open→open` 在 MySQL 返回 rowcount=0，原 CAS 守卫会误抛冲突）。
- `_now` / `_conflict_err`：CAS 落空 → 409 ERR_CLUSTER_0002。

人工侧的 fix_version 归一（trim/lower）已随写面删除 —— `fix_version` 概念在 35-A 即已
退出判定链（K 序列改对全历史重放、无版本下界）。
"""
from datetime import datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.error_flow import ConversionRecord, ErrorCaseLink, ErrorCluster

AUTO_FIXED_K_KEY = "auto_fixed_k_default"   # dict_config 全局键（seed 默认 2）
CLAIM_TTL_DAYS_KEY = "claim_ttl_days"       # dict_config 全局键（seed 默认 14）
CLAIM_TTL_DEFAULT_DAYS = 14
REVIEW_REASONS = ("na", "reentry_same_version", "input_truncated")

CONV_DETAIL_MAX = 1024  # conversion_record.detail VARCHAR(1024)（strict 超长会 DataError）

def _now() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc).replace(tzinfo=None)

def _conflict_err(cluster_id: int) -> AppError:
    """CAS 竞态落空 → 409 带当前状态（后到者；ERR_CLUSTER_0002 本批激活）。"""
    return AppError("ERR_CLUSTER_0002", f"cluster {cluster_id} 已被并发处置，请刷新", http=409)


async def _mark_pending_links(
    session: AsyncSession, cluster_id: int, verify_status: str
) -> int:
    """现行 pending link → 终态（superseded 停回查 / passed / failed），释放 cur_key。"""
    result = await session.execute(
        update(ErrorCaseLink)
        .where(
            ErrorCaseLink.cluster_id == cluster_id,
            ErrorCaseLink.verify_status == "pending",
        )
        .values(verify_status=verify_status)
    )
    return result.rowcount or 0

async def _apply_auto_fixed(session: AsyncSession, cluster_id: int, *, seq_desc: str) -> None:
    """verify K 满收敛：open→fixed（closed_by=auto_regression）。

    批 35-A（online 只读化）：准入由 `claim` 改 `open`。不再有人工认领 ⇒ `claim` 态不可达，
    活动态只剩 `open`；沿用 `claim` 会让自动收口永远进不去（`open → claim` 是它唯一入口）。
    """
    result = await session.execute(
        update(ErrorCluster)
        .where(ErrorCluster.id == cluster_id, ErrorCluster.status == "open")
        .values(status="fixed")
    )
    if result.rowcount != 1:
        raise _conflict_err(cluster_id)
    session.add(ConversionRecord(
        cluster_id=cluster_id, action="auto_fixed", detail=f"K 满纯净序列（{seq_desc}）",
        closed_by="auto_regression", actor_user_id=None))


async def _apply_verify_reopen(session: AsyncSession, cluster_id: int, *, detail: str) -> None:
    """回归 failed：簇留在活动态、K 清零（只记 conv）。

    批 35-A：原实现是 `claim → open` 的 CAS。online 只读化后活动态就是 `open`，该 update
    退化成 `open → open`，而 **MySQL 对「值未变」的 UPDATE 返回 rowcount=0**（未开
    CLIENT_FOUND_ROWS），原 CAS 守卫会误抛 `_conflict_err` 把整条判定链炸掉 —— 故此处
    **只记 conv、不做 UPDATE**。链的推进由调用方 `_mark_pending_links(failed)` 让 link
    离开 pending 承载（assemble_job 据此重新组装）。
    """
    session.add(ConversionRecord(
        cluster_id=cluster_id, action="reopen", detail=f"回归 failed → open（{detail}）",
        actor_user_id=None))


# 批 35-A：`_apply_needs_review` 已删除 —— 全自动下 needs_review 不再是一个状态
# （进了就没人能救它出去，因为唯一的出口 resolve 是人工动作）。判定信号改为在
# `verify.judge_link` 循环内按「仅触发记录」记一条 conv，状态机不动。见 `decide_k`。
