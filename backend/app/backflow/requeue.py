"""backflow 重推计数（detail §7.4 R-7「可愈性标注」的数据源 = 行为数据）。

- `requeue_counts`：成批取各 link **历史** requeue 次数 → {link_id: count}（读面用）。
  口径 = 不含本次（只数已落库的 conversion_record(action=requeue) 行）。

⚠️ 批 35-B：人工失效 / 重推 / 复位的**写面已整体撤除**（`requeue_guard_errors` /
`requeue_link` / `requeue_batch` / `invalidate_link` 及其端点 + UI）。online 只读，处置由
offline 定时拉取完成。随守卫链一并删除的还有三个**只被它消费**的常量
（REQUEUE_DEBOUNCE_MINUTES / REQUEUE_ALLOWED_CLUSTER / CAP_GAP_REASON）—— 勿把注释里的旧
规则（防抖 5min / 状态白名单 / cap_gap 禁推）当现行规则读回，它们已无代码承载。
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.error_flow import ConversionRecord

# R-7 可愈性标注（换判据 = 行为数据）：已重推过 ≥该次数仍 invalidated 回来 = 疑似不可自愈
# （如版本不识别 / 配置长期未补齐），前端据此转强确认（二次确认）。该值系拍定、无数据支撑，
# 上线后按真实 conversion_record 分布调。
# 本常量在后端**零引用点**（仅声明，判据由前端执行）——**唯一行为源 = 前端
# BackflowClusterDetailView.vue 的同名常量**。改阈值须同改三处：本处 + 前端常量 +
# tests/test_backflow_requeue_count.py 的 `== 2` 断言（详见 register R-7「阈值」段）。
SUSPECT_REQUEUE_THRESHOLD = 2


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


