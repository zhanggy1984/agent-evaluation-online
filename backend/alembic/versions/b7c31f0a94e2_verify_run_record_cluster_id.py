"""verify_run_record: 幂等键 link_id → cluster_id

Revision ID: b7c31f0a94e2
Revises: 821efe0a89c0

**为什么**：`uk_verify_run(link_id, run_id)` 的 `link_id` 是推送时现算的——link 在 pending 时
等于其 cluster_id，link 被判出终态后退化为哨兵 0 ⇒ 同一 (簇, run) 在 link 生命周期两侧落在
两个键上，重推（fire-and-forget 的「响应丢失」场景）不命中首推行；而 0 被所有簇共用，后到的
簇会命中别的簇的行（真机实测，见 `models/error_flow.py` 的 `cluster_id` 列注释）。

**回填**：link 行取 link.cluster_id；orphan 行（link_id=0）取载荷留档
`raw_json.trigger_signal_id`。**取不到就报错中断**，不静默写哨兵。

**归并（本迁移的第二步，实测必需）**：旧键下，一笔推送可能落**两行**——首推落 link 行、
重推（link 已终态 ⇒ 走 orphan）再落一行哨兵行。回填后二者同簇同 run，撞新唯一键（实测
dev 库：`(3846, 3059)` 双行）。归并规则刻意收窄：**只删 orphan 行（link_id=0）中与 link 行
重复的那些**——它不携带 link 行没有的信息（载荷 raw_json 相同、case_pass 反是 NULL）。
**两行都带 link 时不删**（那可能是同簇两个 link 各推过一笔，是真实历史），而是报错中断交人工。

**可重入**：本迁移首次执行时曾在「建新唯一键」一步失败（撞上面那个重复）——那时列已加、
NOT NULL 已收紧、旧唯一键已删，即库停在半迁移态。故此处每步都先探测现状，
重跑即可收敛，不需要手工修库。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "b7c31f0a94e2"
down_revision: Union[str, None] = "821efe0a89c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "verify_run_record"


def _unique_names() -> set:
    insp = sa.inspect(op.get_bind())
    return {u["name"] for u in insp.get_unique_constraints(_TABLE)}


def upgrade() -> None:
    bind = op.get_bind()

    # 1) 加列（先可空：回填完成前无法满足 NOT NULL；已存在则跳过）
    cols = {c["name"] for c in sa.inspect(bind).get_columns(_TABLE)}
    if "cluster_id" not in cols:
        op.add_column(
            _TABLE,
            sa.Column("cluster_id", mysql.BIGINT(unsigned=True), nullable=True,
                      comment="幂等键与归属的簇锚（= 载荷 trigger_signal_id）"),
        )

    # 2) link 行：以现行 link 的簇为准（有 link 时二者恒等，这是权威来源）
    op.execute(
        f"UPDATE {_TABLE} r JOIN error_case_link l ON l.id = r.link_id "
        "SET r.cluster_id = l.cluster_id WHERE r.cluster_id IS NULL"
    )

    # 3) orphan 行：从载荷原样留档派生（`->>` 返回字符串，CAST 成无符号整数）
    op.execute(
        f"UPDATE {_TABLE} SET cluster_id = "
        "CAST(raw_json->>'$.trigger_signal_id' AS UNSIGNED) "
        "WHERE cluster_id IS NULL AND raw_json->>'$.trigger_signal_id' IS NOT NULL"
    )

    # 4) 仍为空的：**中断**（不猜）——既无 link 也无留档簇 id，回填无据
    left = bind.execute(sa.text(
        f"SELECT id, link_id, run_id FROM {_TABLE} WHERE cluster_id IS NULL"
    )).fetchall()
    if left:
        raise RuntimeError(
            f"{_TABLE} 有 {len(left)} 行无法回填 cluster_id（既无现行 link、留档也无 "
            f"trigger_signal_id）：{left}。本迁移不做猜测——请人工定夺这些行的簇归属后重跑。"
        )

    # 5) 归并：旧键留下的「link 行 + 重放 orphan 行」在 (簇, run) 上重复。
    #    只删 orphan 侧（见模块 docstring 的收窄理由）。
    op.execute(
        f"DELETE o FROM {_TABLE} o JOIN {_TABLE} k "
        "ON k.cluster_id = o.cluster_id AND k.run_id = o.run_id AND k.id <> o.id "
        "WHERE o.link_id = 0"
    )
    # 5b) 剩余冲突 = 两行都带 link（真实历史，删不得）→ 中断交人工
    dups = bind.execute(sa.text(
        f"SELECT cluster_id, run_id, COUNT(*) c FROM {_TABLE} "
        "GROUP BY cluster_id, run_id HAVING c > 1"
    )).fetchall()
    if dups:
        raise RuntimeError(
            f"{_TABLE} 仍有 (cluster_id, run_id) 重复且两侧都带 link：{dups}。"
            f"这说明同一簇的两个 link 各推过同一 run——不是可自动归并的冗余，请人工定夺。"
        )

    # 6) 收紧为 NOT NULL（NULL 在唯一索引中不去重，留着等于给幂等键开洞）
    op.alter_column(_TABLE, "cluster_id",
                    existing_type=mysql.BIGINT(unsigned=True), nullable=False)

    # 7) 换唯一键（旧键可能已在半迁移态中被删掉，故先探测）
    if "uk_verify_run" in _unique_names():
        op.drop_constraint("uk_verify_run", _TABLE, type_="unique")
    op.create_unique_constraint("uk_verify_run", _TABLE, ["cluster_id", "run_id"])


def downgrade() -> None:
    if "uk_verify_run" in _unique_names():
        op.drop_constraint("uk_verify_run", _TABLE, type_="unique")
    op.create_unique_constraint("uk_verify_run", _TABLE, ["link_id", "run_id"])
    op.drop_column(_TABLE, "cluster_id")
