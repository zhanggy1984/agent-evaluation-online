"""error 回流核心域（detail §5.1④⑤⑥⑦⑦b⑩）：cluster/link/回查/审计/批/判定态。

关键语义：
- error_case_link.cur_key 为 MySQL 生成列（§5.1 注）——仅 verify_status='pending' 时取
  cluster_id、终态自动置 NULL 释放占位；uk_link_current(case_type, cur_key) 由此保证同
  cluster 同 case_type 至多一条现行 link。模型用 Computed() 表达，ORM 只读。
- trace_judge_state 为消费侧累积判定态（judge_scan_job 执行方）；root_input_hash =
  sha256(normalize(input))，与 error_cluster.input_hash 同源可比（§6.2）。
"""
from datetime import datetime

from sqlalchemy import CHAR, JSON, Computed, Enum, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BIGINT_UX, DT3, TINYINT, TINYINT_UX, TS_DEFAULT, TS_UPDATE, Base


class ErrorCluster(Base):
    """错误聚类：error 去重键(agent+interface+error_type+input_hash) × generation。"""

    __tablename__ = "error_cluster"

    id: Mapped[int] = mapped_column(BIGINT_UX, primary_key=True, autoincrement=True)
    agent: Mapped[str] = mapped_column(String(64), nullable=False)
    interface: Mapped[str] = mapped_column(String(256), nullable=False)
    layer: Mapped[str] = mapped_column(
        Enum("L1", "L2", name="cluster_layer", native_enum=True), nullable=False
    )
    error_type: Mapped[str] = mapped_column(String(48), nullable=False)  # error_type 原值
    input_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)  # sha256(normalize(input))
    # 代表事件 input 实文（脱敏+截断≤8K，组装取数源，不依赖 ES 回读）
    input_snapshot: Mapped[str | None] = mapped_column(mysql.MEDIUMTEXT(), nullable=True)
    input_truncated: Mapped[int] = mapped_column(TINYINT, nullable=False, server_default=text("0"))
    error_msg: Mapped[str] = mapped_column(String(512), nullable=False)  # 脱敏错误摘要
    first_trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger_version: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 仅溯源
    first_ts: Mapped[datetime] = mapped_column(DT3, nullable=False)
    latest_ts: Mapped[datetime] = mapped_column(DT3, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    generation: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    status: Mapped[str] = mapped_column(
        Enum(
            "open", "claim", "fixed", "inactive", "needs_review",
            name="cluster_status", native_enum=True,
        ),
        nullable=False,
        server_default=text("'open'"),
    )
    fix_version: Mapped[str | None] = mapped_column(String(64), nullable=True)  # claim 时填写
    claimed_by: Mapped[int | None] = mapped_column(BIGINT_UX, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DT3, nullable=True)
    claim_due_ts: Mapped[datetime | None] = mapped_column(DT3, nullable=True)  # 复核窗 TTL
    claim_k: Mapped[int] = mapped_column(TINYINT_UX, nullable=False, server_default=text("2"))
    needs_review_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DT3, nullable=False, server_default=TS_DEFAULT)
    updated_at: Mapped[datetime] = mapped_column(DT3, nullable=False, server_default=TS_UPDATE)

    __table_args__ = (
        UniqueConstraint(
            "agent", "interface", "error_type", "input_hash", "generation", name="uk_cluster_dedup"
        ),
        Index("idx_cluster_list", "status", "first_ts"),
        Index("idx_cluster_watch", "agent", "interface", "error_type", "input_hash"),
        {"comment": "错误聚类（error 去重键 + 快照 + 代数）"},
    )


class ErrorCaseLink(Base):
    """回流用例关联：offline 镜像 + pull 传输；payload_id = D19 幂等键（uuid4）。"""

    __tablename__ = "error_case_link"

    id: Mapped[int] = mapped_column(BIGINT_UX, primary_key=True, autoincrement=True)
    cluster_id: Mapped[int] = mapped_column(BIGINT_UX, nullable=False)
    payload_id: Mapped[str] = mapped_column(CHAR(36), nullable=False)
    case_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # offline case id
    case_type: Mapped[str] = mapped_column(
        Enum("regression_error", name="link_case_type", native_enum=True),
        nullable=False,  # v1 白名单仅此；二期加值须回方案
    )
    source_trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger_version: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 仅溯源
    fix_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_truncated: Mapped[int] = mapped_column(TINYINT, nullable=False, server_default=text("0"))
    offline_status: Mapped[str] = mapped_column(
        Enum(
            "assembled", "draft", "active", "invalidated",
            name="link_offline_status", native_enum=True,
        ),
        nullable=False,
        server_default=text("'assembled'"),
    )
    verify_status: Mapped[str] = mapped_column(
        Enum(
            "pending", "passed", "failed", "invalidated", "superseded",
            name="link_verify_status", native_enum=True,
        ),
        nullable=False,
        server_default=text("'pending'"),
    )
    payload_json: Mapped[str] = mapped_column(mysql.MEDIUMTEXT(), nullable=False)  # D19 信封完整体
    assembled_ts: Mapped[datetime] = mapped_column(DT3, nullable=False, server_default=TS_DEFAULT)
    invalidate_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    invalidated_by: Mapped[int | None] = mapped_column(BIGINT_UX, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DT3, nullable=False, server_default=TS_DEFAULT)
    updated_at: Mapped[datetime] = mapped_column(DT3, nullable=False, server_default=TS_UPDATE)
    cur_key: Mapped[int | None] = mapped_column(
        BIGINT_UX,
        Computed("IF(verify_status = 'pending', cluster_id, NULL)", persisted=True),
        nullable=True,  # 现行位：仅 pending 占位、终态自动释放（生成列只读）
    )

    __table_args__ = (
        UniqueConstraint("payload_id", name="uk_link_payload"),
        UniqueConstraint("case_type", "cur_key", name="uk_link_current"),
        Index("idx_link_pull", "offline_status", "assembled_ts"),
        Index("idx_link_verify", "verify_status"),
        {"comment": "回流用例关联（offline 镜像 + pull 传输）"},
    )


class VerifyRunRecord(Base):
    """复验回查历史：回归 run 单错级结果 × 版本时间线（跨版本稳定序列 K 的载体）。"""

    __tablename__ = "verify_run_record"

    id: Mapped[int] = mapped_column(BIGINT_UX, primary_key=True, autoincrement=True)
    link_id: Mapped[int] = mapped_column(BIGINT_UX, nullable=False)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)  # offline run id
    bound_version: Mapped[str] = mapped_column(String(64), nullable=False)  # 该 run 绑定 agent 版本
    case_pass: Mapped[int | None] = mapped_column(TINYINT, nullable=True)  # null = pass_fail 'na'
    run_status: Mapped[str] = mapped_column(String(16), nullable=False)  # run 终态字面量
    raw_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # run_results 原样留档
    verified_ts: Mapped[datetime] = mapped_column(DT3, nullable=False, server_default=TS_DEFAULT)

    __table_args__ = (
        UniqueConstraint("link_id", "run_id", name="uk_verify_run"),
        {"comment": "回归 run 单错级结果（终态只读）"},
    )


class ConversionRecord(Base):
    """回流/人工处置审计：trace→case→人工处置全链。"""

    __tablename__ = "conversion_record"

    id: Mapped[int] = mapped_column(BIGINT_UX, primary_key=True, autoincrement=True)
    cluster_id: Mapped[int | None] = mapped_column(BIGINT_UX, nullable=True)
    link_id: Mapped[int | None] = mapped_column(BIGINT_UX, nullable=True)
    action: Mapped[str] = mapped_column(String(48), nullable=False)  # assemble/claim/ignore/…
    detail: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    closed_by: Mapped[str | None] = mapped_column(
        Enum("auto_regression", "admin_review", name="closed_by", native_enum=True), nullable=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(BIGINT_UX, nullable=True)  # 系统动作记 NULL
    ts: Mapped[datetime] = mapped_column(DT3, nullable=False, server_default=TS_DEFAULT)

    __table_args__ = (
        Index("idx_conv_cluster", "cluster_id"),
        {"comment": "回流审计（trace→case→人工处置）"},
    )


class NeedsReviewBatch(Base):
    """回归 na 聚合批：同 run 同 error_type 一条（仅承载 unclean_run 批，§7.6）。"""

    __tablename__ = "needs_review_batch"

    id: Mapped[int] = mapped_column(BIGINT_UX, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)  # offline error run id
    agent: Mapped[str] = mapped_column(String(64), nullable=False)
    bound_version: Mapped[str] = mapped_column(String(64), nullable=False)  # = claim fix_version
    error_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("open", "resolved", name="batch_status", native_enum=True),
        nullable=False,
        server_default=text("'open'"),
    )
    # link_refs = [{link_id, cluster_id, case_id}]（run 缺行 case 不产生）
    link_refs: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)  # unclean_run 附注
    resolve_action: Mapped[str | None] = mapped_column(String(24), nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(BIGINT_UX, nullable=True)
    created_ts: Mapped[datetime] = mapped_column(DT3, nullable=False, server_default=TS_DEFAULT)
    resolved_ts: Mapped[datetime | None] = mapped_column(DT3, nullable=True)

    __table_args__ = (
        UniqueConstraint("run_id", "agent", "bound_version", "error_type", name="uk_batch_agg"),
        Index("idx_batch_status", "status"),
        {"comment": "回归 na 聚合批（整批同动作单事务处置）"},
    )


class TraceJudgeState(Base):
    """消费侧 trace 累积判定态（judge_scan_job 执行方；重平衡从本表重建不回读 ES）。"""

    __tablename__ = "trace_judge_state"

    id: Mapped[int] = mapped_column(BIGINT_UX, primary_key=True, autoincrement=True)
    agent: Mapped[str] = mapped_column(String(64), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    root_ok: Mapped[int] = mapped_column(TINYINT, nullable=False, server_default=text("0"))
    root_ts: Mapped[datetime | None] = mapped_column(DT3, nullable=True)
    interface: Mapped[str | None] = mapped_column(String(256), nullable=True)
    root_status: Mapped[str | None] = mapped_column(String(16), nullable=True)  # ok/error/timeout
    root_error_type: Mapped[str | None] = mapped_column(String(48), nullable=True)
    root_input_hash: Mapped[str | None] = mapped_column(CHAR(64), nullable=True)
    # root input 脱敏截断≤8K 明文快照（消费 step4 root 到达同刻落库，唯一见原始明文处）
    input_snapshot_clean: Mapped[str | None] = mapped_column(mysql.MEDIUMTEXT(), nullable=True)
    input_truncated: Mapped[int] = mapped_column(TINYINT, nullable=False, server_default=text("0"))
    err_summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 子节点 error 汇总
    llm_fact_ok: Mapped[int] = mapped_column(TINYINT, nullable=False, server_default=text("0"))
    # judged = classify 完成；processed = 进聚类处理完（judged/processed 分离，防重放）
    judged: Mapped[int] = mapped_column(TINYINT, nullable=False, server_default=text("0"))
    processed: Mapped[int] = mapped_column(TINYINT, nullable=False, server_default=text("0"))
    # root 在 judged=1 后迟到 → root 级补判已触发标记（§4.3④/§4.4）
    root_late_complement: Mapped[int] = mapped_column(
        TINYINT, nullable=False, server_default=text("0")
    )
    judgement_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 判定产出
    ttl_until: Mapped[datetime] = mapped_column(DT3, nullable=False)  # judge_scan_job 扫描位点
    updated_ts: Mapped[datetime] = mapped_column(DT3, nullable=False, server_default=TS_UPDATE)

    __table_args__ = (
        UniqueConstraint("agent", "trace_id", name="uk_trace"),
        Index("idx_judge_scan", "judged", "ttl_until"),
        Index("idx_purge", "processed", "updated_ts"),
        {"comment": "消费侧 trace 累积判定态"},
    )
