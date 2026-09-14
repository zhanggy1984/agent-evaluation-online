"""admin 系统管理面：配置管理 + 用户管理（detail §8.6）、agent 与接口字典（§8.5）。
全部端点 `AdminUser` 依赖。

**§8.5 分两批**（用户 2026-09-14 拍板「拆细、单独验证」）：本文件当前含**字典面**四端点
（`/agents`、`/agents/{id}/toggle`、`/agents/{id}/interfaces`、`/interfaces/{id}`），
读 MySQL 两表；`/agents/{id}/health` 读 ES 事件 index、本环境可能无心跳数据 ⇒ 单独成批，
避免「字典面全绿」掩盖「health 只验了空态」。凭证两端点（`credential` 读 + `rotate`）
另批。

**零 DDL 实现基础**（逐字段核对，非推断）：
- 配置写入/version：`dict_config`（`uk_dc(agent_id, config_key)`、`config_value` JSON、`version`）。
- 变更审计：`conversion_record`（`cluster_id`/`link_id` 可空 → 配置变更无 cluster；
  `action` 是 `String(48)` 自由文本 → 无需改枚举；`detail` 上限 1024）。
- 禁用即失效：`user.status` + `user_session.revoked_at` 两半
  （**与 `api/auth.py` 的实机机制一致**）。

**键清单不新造第二份**：v1 生效键 = `core/seed.py` 的 `GLOBAL_DEFAULTS` / `PER_AGENT_DEFAULTS`。
仓内已有「阈值双份硬编码」前车之鉴，故本面**只引用** seed 的常量，不另立清单。

**边界（显式）**：
- `§8.9` 的 `ERR_CONFIG_0001` 在本面**首次有抛出点**（此前零抛出点）；http 取 **400**（非法 key /
  value 形状 / 未知 agent / 用户名重复 等**参数类**拒绝），**403 的「角色不足」由 `require_admin`
  以 `ERR_AUTH_0002` 承担**——两种拒绝语义不同码不同，不合并。
- 自锁防护：**不允许停用自己、不允许改自己的角色**（否则可能锁死 admin 面且无恢复入口）。
- 审计筛选 v1 只做 `action` + `actor_user_id` + 时间窗；按 `config_key` 筛选**未做**（`detail`
  是自由文本无索引，要做需加列 = 破零 DDL），登记为已知限制。
"""
import json
from collections import Counter
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser
from app.api.schemas import (
    AgentAdminOut,
    ConfigItem,
    ConfigUpdateRequest,
    InterfaceAdminOut,
    InterfaceListOut,
    InterfaceUpdateRequest,
    UserAdminOut,
    UserCreateRequest,
    UserUpdateRequest,
)
from app.core import dict_config
from app.core.db import get_session
from app.core.errors import AppError
from app.core.log import get_logger
from app.core.security import hash_password
from app.core.seed import GLOBAL_DEFAULTS, PER_AGENT_DEFAULTS
from app.models.agent import Agent, Interface
from app.models.config import DictConfig
from app.models.error_flow import ConversionRecord
from app.models.user import User, UserSession

router = APIRouter(prefix="/admin", tags=["admin"])

logger = get_logger("app.api.admin")

_Session = Annotated[AsyncSession, Depends(get_session)]

ACTION_CONFIG_CHANGE = "config_change"

# 审计 detail 上限（models/error_flow.py:156 = String(1024)）；两侧值各留 _SIDE_MAX，
# 超出时显式标注截断。
_DETAIL_MAX = 1024
_SIDE_MAX = 400


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _allowed(agent_id: int | None) -> dict[str, Any]:
    """键清单：agent_id 缺省（None）= 全局键，给了 = per-agent 键（与 seed 的落库口径同源）。"""
    return PER_AGENT_DEFAULTS if agent_id is not None else GLOBAL_DEFAULTS


def _require_known_key(agent_id: int | None, key: str) -> Any:
    """键必须落在 v1 生效清单内，返回其默认值（供校验 value 形状）。"""
    defaults = _allowed(agent_id)
    if key not in defaults:
        scope = f"agent {agent_id}" if agent_id is not None else "全局"
        raise AppError(
            "ERR_CONFIG_0001",
            f"{scope}配置键不存在或非 v1 生效键：{key}",
            http=400,
        )
    return defaults[key]


def _check_value_shape(key: str, value: Any, default: Any) -> None:
    """value 形状按该键默认值类型校验（bool 是 int 子类，须先判）。

    空词表合法——它是 fail-closed 的载体（§6.3 step3），不在此拦。
    """
    if isinstance(default, bool):
        ok = isinstance(value, bool)
    elif isinstance(default, int):
        ok = isinstance(value, int) and not isinstance(value, bool)
    elif isinstance(default, list):
        ok = isinstance(value, list) and all(isinstance(x, str) for x in value)
    else:
        ok = isinstance(value, type(default))
    if not ok:
        raise AppError(
            "ERR_CONFIG_0001",
            f"配置键 {key} 的值形状不符：期望 {type(default).__name__}",
            http=400,
        )


def _summarize(value: Any) -> str:
    """审计用值摘要：超长截断并**显式标注**（防审计读者把截断值当成全值）。"""
    text = json.dumps(value, ensure_ascii=False)
    if len(text) <= _SIDE_MAX:
        return text
    return f"{text[:_SIDE_MAX]}…(截断，全值 {len(text)} 字符)"


async def _get_agent_id(agent_id: int, session: AsyncSession) -> None:
    """per-agent 键写入前校验 agent 存在（防写出无主配置行）。"""
    exists = await session.scalar(select(Agent.id).where(Agent.id == agent_id))
    if exists is None:
        raise AppError("ERR_CONFIG_0001", f"agent 不存在：{agent_id}", http=400)


def _to_item(row: DictConfig | None, key: str, agent_id: int | None, default: Any) -> ConfigItem:
    if row is None:
        return ConfigItem(agent_id=agent_id, key=key, value=default, version=0, is_default=True)
    return ConfigItem(
        agent_id=row.agent_id,
        key=row.config_key,
        value=row.config_value,
        version=row.version,
        updated_by=row.updated_by,
        updated_ts=row.updated_ts,
    )


# ---------- 配置（§8.6） ----------


@router.get("/configs", response_model=list[ConfigItem])
async def list_configs(user: AdminUser, session: _Session, agent: int | None = None) -> list:
    """v1 生效键全量：库内有行的给出实际值/version，缺行的按 seed 默认值补位（is_default=True）。

    只返回 v1 生效键（二期键不建）；`agent` 缺省 = 全局键（agent_id IS NULL）。
    """
    logger.debug("admin configs 入参: admin=%s agent=%s", user.username, agent)
    defaults = _allowed(agent)
    stmt = select(DictConfig).where(DictConfig.config_key.in_(list(defaults)))
    stmt = stmt.where(
        DictConfig.agent_id.is_(None) if agent is None else DictConfig.agent_id == agent
    )
    rows = {r.config_key: r for r in (await session.execute(stmt)).scalars().all()}
    out = [_to_item(rows.get(k), k, agent, d) for k, d in defaults.items()]
    logger.debug("admin configs 出参: 键数=%s", len(out))
    return out


@router.put("/configs", response_model=ConfigItem)
async def put_config(
    body: ConfigUpdateRequest, user: AdminUser, session: _Session
) -> ConfigItem:
    """写配置：键/形状校验 → upsert → `version + 1` → 写审计（`config_change`）→ 清读缓存。

    `fallback_utterance` 走同一路径不特判：其 `version` 即 D19 `wordlist_version`。
    """
    logger.debug(
        "admin 配置写入 入参: admin=%s agent=%s key=%s value摘要=%s",
        user.username,
        body.agent_id,
        body.key,
        _summarize(body.value),
    )
    key = body.key.strip()
    default = _require_known_key(body.agent_id, key)
    _check_value_shape(key, body.value, default)
    if body.agent_id is not None:
        await _get_agent_id(body.agent_id, session)

    stmt = select(DictConfig).where(DictConfig.config_key == key)
    stmt = stmt.where(
        DictConfig.agent_id.is_(None)
        if body.agent_id is None
        else DictConfig.agent_id == body.agent_id
    )
    row = (await session.execute(stmt)).scalar_one_or_none()

    old_value = row.config_value if row is not None else None
    old_version = row.version if row is not None else 0
    if row is None:
        # 注意：MySQL 唯一索引对 NULL 不去重，全局键无法靠 ON DUPLICATE KEY 兜底 →
        # 走「先查后插」，单实例（uvicorn --workers 1）语义下无并发写同一键的窗口。
        row = DictConfig(
            agent_id=body.agent_id, config_key=key, config_value=body.value, version=1
        )
        session.add(row)
    else:
        row.config_value = body.value
        row.version = (row.version or 0) + 1
    row.updated_by = user.username
    row.updated_ts = _utcnow_naive()

    scope = f"agent:{body.agent_id}" if body.agent_id is not None else "global"
    detail = (
        f"{scope} 配置 {key} v{old_version}→{row.version}："
        f"{_summarize(old_value)} → {_summarize(body.value)}"
    )
    if len(detail) > _DETAIL_MAX:
        detail = detail[: _DETAIL_MAX - 12] + "…(整体截断)"
    session.add(
        ConversionRecord(
            cluster_id=None,
            link_id=None,
            action=ACTION_CONFIG_CHANGE,
            detail=detail,
            actor_user_id=user.id,
        )
    )
    # 提交**前**组装响应：commit 后 ORM 实例可能过期，读属性会触发懒刷新
    # （async 下 = MissingGreenlet；生产 get_session 虽为 expire_on_commit=False，但不应依赖之）
    out = _to_item(row, key, body.agent_id, default)
    await session.commit()
    # 读侧 60s 进程内缓存（core/dict_config）：写入后立即清，使变更即时生效
    dict_config.invalidate_cache()
    logger.debug(
        "admin 配置写入 出参: key=%s agent=%s version=%s", key, body.agent_id, out.version
    )
    return out


# ---------- 用户（§8.6） ----------


def _user_out(u: User) -> UserAdminOut:
    return UserAdminOut(
        id=u.id,
        username=u.username,
        display_name=u.display_name,
        role=u.role,
        status=u.status,
        created_at=u.created_at,
    )


async def _revoke_sessions(session: AsyncSession, user_id: int) -> int:
    """撤销该用户全部未撤销会话（§8.6「禁用即吊销」的两半之一；另一半 = status=0）。"""
    rows = (
        (
            await session.execute(
                select(UserSession).where(
                    UserSession.user_id == user_id, UserSession.revoked_at.is_(None)
                )
            )
        )
        .scalars()
        .all()
    )
    now = _utcnow_naive()
    for r in rows:
        r.revoked_at = now
    return len(rows)


@router.get("/users", response_model=list[UserAdminOut])
async def list_users(user: AdminUser, session: _Session) -> list[UserAdminOut]:
    logger.debug("admin users 入参: admin=%s", user.username)
    rows = (await session.execute(select(User).order_by(User.id))).scalars().all()
    out = [_user_out(u) for u in rows]
    logger.debug("admin users 出参: 账号数=%s", len(out))
    return out


@router.post("/users", response_model=UserAdminOut, status_code=201)
async def create_user(
    body: UserCreateRequest, user: AdminUser, session: _Session
) -> UserAdminOut:
    """建号。口令最小规则 = 长度 8~64（schema 层），**不做复杂度要求**（v1 单团队内部系统）。"""
    # 出/入参日志不打口令（§口令类值一律不进日志）
    logger.debug(
        "admin 建号 入参: admin=%s username=%s role=%s", user.username, body.username, body.role
    )
    username = body.username.strip()
    if body.role not in ("admin", "viewer"):
        raise AppError("ERR_CONFIG_0001", f"角色非法：{body.role}", http=400)
    if not username:
        raise AppError("ERR_CONFIG_0001", "用户名不能为空", http=400)
    exists = await session.scalar(select(User.id).where(User.username == username))
    if exists is not None:
        raise AppError("ERR_CONFIG_0001", f"用户名已存在：{username}", http=400)

    row = User(
        username=username,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        role=body.role,
        status=1,
    )
    session.add(row)
    await session.commit()
    # 显式 refresh：created_at 是服务端默认列，插入后**从未加载**，直接读属性在 async 下
    # 会触发同步懒刷新 → MissingGreenlet（expire_on_commit=False 也挡不住这一类）
    await session.refresh(row)
    out = _user_out(row)
    logger.debug("admin 建号 出参: id=%s username=%s", out.id, out.username)
    return out


@router.put("/users/{uid}", response_model=UserAdminOut)
async def update_user(
    uid: int, body: UserUpdateRequest, user: AdminUser, session: _Session
) -> UserAdminOut:
    """改显示名/角色/启停/重置口令。

    **语义（明写，防误读）**：字段缺省 = 不修改（`None` 不代表清空）；
    **停用（`status=0`）与重置口令都会撤销该用户全部未撤销会话**（`revoked_at` 落时），
    即时生效机制 = `user.status` + `user_session` 两半（**不是**文档旧文里的 token version）。
    """
    logger.debug(
        "admin 改号 入参: admin=%s uid=%s 字段=%s",
        user.username,
        uid,
        sorted(body.model_dump(exclude_none=True).keys()),
    )
    row = await session.get(User, uid)
    if row is None:
        raise AppError("ERR_CONFIG_0001", f"用户不存在：{uid}", http=400)

    if uid == user.id:
        if body.status is not None and body.status != row.status:
            raise AppError("ERR_CONFIG_0001", "不能启停自己（防锁死 admin 面）", http=400)
        if body.role is not None and body.role != row.role:
            raise AppError("ERR_CONFIG_0001", "不能修改自己的角色（防锁死 admin 面）", http=400)

    if body.role is not None:
        if body.role not in ("admin", "viewer"):
            raise AppError("ERR_CONFIG_0001", f"角色非法：{body.role}", http=400)
        row.role = body.role
    if body.display_name is not None:
        row.display_name = body.display_name
    if body.password is not None:
        row.password_hash = hash_password(body.password)
    if body.status is not None:
        if body.status not in (0, 1):
            raise AppError("ERR_CONFIG_0001", f"status 非法：{body.status}", http=400)
        row.status = body.status

    revoked = 0
    if (body.status is not None and body.status == 0) or body.password is not None:
        revoked = await _revoke_sessions(session, uid)
    out = _user_out(row)  # 同上：提交前取值
    await session.commit()
    if revoked:
        logger.info("账号变更连带吊销会话：user_id=%s 吊销 %s 个", uid, revoked)
    logger.debug(
        "admin 改号 出参: uid=%s role=%s status=%s 吊销会话=%s",
        uid,
        out.role,
        out.status,
        revoked,
    )
    return out


# ---------- agent 与接口字典（§8.5） ----------
#
# 本段 = §8.5 的**字典面**（读 MySQL 的 `agent`/`interface` 两表）；§8.5 的 `health`
# 读的是 ES 事件 index，验证面完全不同（本环境可能无心跳 doc ⇒ 只能验空态），
# 单独成批，不与此处混交——防「前四端全绿」把「health 只验了空态」盖掉。

ACTION_AGENT_TOGGLE = "agent_toggle"
ACTION_INTERFACE_CHANGE = "interface_dict_change"

# 接口字典单次返回上限：§8.5 未定义分页入参 ⇒ v1 全量返回，超限截断并置 truncated。
_INTERFACE_MAX = 500

# 本端点只产出「人工补标」。`config`（离线配置推导）与 `auto_observed`（观测自动写入）
# 都不是 admin 手改的产物——接受它们会让 `updated_by`/审计失去「谁改的」语义。
_ADMIN_LLM_SOURCES = ("manual",)


def _enum_str(v: Any) -> Any:
    """取 Enum 列的字面值（替身/纯字符串场景原样返回）。"""
    return getattr(v, "value", v)


def _agent_out(row: Agent, interface_count: int) -> AgentAdminOut:
    return AgentAdminOut(
        id=row.id,
        name=row.name,
        display_name=row.display_name,
        enable=row.enable,
        backflow_allow=row.backflow_allow,
        route_source=_enum_str(row.route_source),
        base_url=row.base_url,
        interface_count=interface_count,
    )


def _interface_out(row: Interface) -> InterfaceAdminOut:
    return InterfaceAdminOut(
        id=row.id,
        agent_id=row.agent_id,
        interface=row.interface,
        method=row.method,
        path=row.path,
        llm=row.llm,
        llm_source=_enum_str(row.llm_source),
        llm_suspect=row.llm_suspect,
        body_search=row.body_search,
        status=row.status,
        first_seen_ts=row.first_seen_ts,
        last_seen_ts=row.last_seen_ts,
        updated_by=row.updated_by,
    )


async def _interface_counts(session: AsyncSession, agent_id: int | None = None) -> Counter:
    """按 agent 汇总接口条数（`agent_id` 给了则只数该 agent）。

    ⚠️ **取整行后在 Python 侧按 `agent_id` 计数，不用 `GROUP BY func.count()`**：替身
    （`tests/_fakes.py`）没有聚合解析分支，用它会让本面在单测里整批不可写。
    也不写 `select(Interface.agent_id)` 取单列——替身**不建模列投影**（列级 select 仍
    返回整行，与其自身注释不符，2026-09-14 实测），那样会得到一个「只在替身下崩」的写法。
    interface 表规模 = 「agent 数 × 接口数」，admin 面 v1 全取可接受；真成瓶颈时再换聚合
    并补替身。
    """
    stmt = select(Interface)
    if agent_id is not None:
        stmt = stmt.where(Interface.agent_id == agent_id)
    rows = (await session.execute(stmt)).scalars().all()
    return Counter(r.agent_id for r in rows)


@router.get("/agents", response_model=list[AgentAdminOut])
async def list_agents(user: AdminUser, session: _Session) -> list[AgentAdminOut]:
    """agent 字典清单。

    ⚠️ **数据源 = MySQL `agent` 表，不是 ES**——与 §8.3 的 `/metrics/agents` 互不替代：
    后者是「近 7d 有流量的 agent 名」实测面，**零流量/已停用的 agent 在其中完全不可见**，
    运维据此分不清「agent 掉线」与「本来就没接」。
    """
    logger.debug("admin agents 入参: admin=%s", user.username)
    rows = (await session.execute(select(Agent).order_by(Agent.id))).scalars().all()
    counts = await _interface_counts(session)
    out = [_agent_out(r, counts.get(r.id, 0)) for r in rows]
    logger.debug("admin agents 出参: agent 数=%s", len(out))
    return out


@router.post("/agents/{agent_id}/toggle", response_model=AgentAdminOut)
async def toggle_agent(agent_id: int, user: AdminUser, session: _Session) -> AgentAdminOut:
    """翻转 `agent.enable`。

    **[裁定]** 无 body：§8.5（detail `:1127`）未定义 toggle 的入参，故语义 = 翻转当前值，
    不要求调用方先读再写（避免读改写竞态）。

    ⚠️ **停用不等于停消费**（§8.5 `:1127` 逐字：「停用仅停回流生成与展示，消费不停」
    ——防数据黑洞）。该语义有真实读侧：`analyzer/classify.py:189-190`/`:226-227` 的
    `agent_enabled` 白名单门 + `consumer/main.py:123` `_enabled_agents()`。
    """
    logger.debug("admin toggle agent 入参: admin=%s agent_id=%s", user.username, agent_id)
    row = await session.get(Agent, agent_id)
    if row is None:
        raise AppError("ERR_CONFIG_0001", f"agent 不存在：{agent_id}", http=400)
    before = row.enable
    row.enable = 0 if before else 1
    counts = await _interface_counts(session, agent_id)
    detail = f"agent={row.name} enable {before}→{row.enable}"
    session.add(
        ConversionRecord(
            cluster_id=None,
            link_id=None,
            action=ACTION_AGENT_TOGGLE,
            detail=detail[:_DETAIL_MAX],
            actor_user_id=user.id,
        )
    )
    # 同批 1：提交前组装（commit 后读 ORM 属性在 async 下会触发懒刷新）
    out = _agent_out(row, counts.get(agent_id, 0))
    await session.commit()
    logger.info("agent 启停：%s enable=%s（admin=%s）", row.name, out.enable, user.username)
    logger.debug("admin toggle agent 出参: agent_id=%s enable=%s", agent_id, out.enable)
    return out


@router.get("/agents/{agent_id}/interfaces", response_model=InterfaceListOut)
async def list_agent_interfaces(
    agent_id: int, user: AdminUser, session: _Session
) -> InterfaceListOut:
    """某 agent 的接口字典（§8.5 `:1128` 字段集）。

    ⚠️ `interface` 串不可改（见 `InterfaceUpdateRequest` 注释）；本端点只读。
    """
    logger.debug("admin agent interfaces 入参: admin=%s agent_id=%s", user.username, agent_id)
    stmt = (
        select(Interface)
        .where(Interface.agent_id == agent_id)
        .order_by(Interface.interface)
        .limit(_INTERFACE_MAX + 1)
    )
    rows = (await session.execute(stmt)).scalars().all()
    truncated = len(rows) > _INTERFACE_MAX
    out = InterfaceListOut(
        items=[_interface_out(r) for r in rows[:_INTERFACE_MAX]], truncated=truncated
    )
    logger.debug(
        "admin agent interfaces 出参: agent_id=%s 条数=%s 截断=%s",
        agent_id,
        len(out.items),
        truncated,
    )
    return out


@router.put("/interfaces/{interface_id}", response_model=InterfaceAdminOut)
async def put_interface(
    interface_id: int, body: InterfaceUpdateRequest, user: AdminUser, session: _Session
) -> InterfaceAdminOut:
    """接口字典人工订正（§8.5 `:1129`，入参 = `{llm?, llm_source?, body_search?}`）。

    **[裁定 1]** `llm_source` 只接受 `manual`（人工补标）。
    **[裁定 2]** `llm=1` 时**连带清 `llm_suspect`**——疑似漏标态由「人工确认 llm」解除。
    **[裁定 3]** **不支持改 `interface` 串**：文档入参里本就没有该字段，而它又是唯一键列
    （`models/agent.py:70` `uk_interface(agent_id, interface)`），改它等于换实体。
    """
    logger.debug(
        "admin 改接口 入参: admin=%s interface_id=%s fields=%s",
        user.username,
        interface_id,
        sorted(body.model_dump(exclude_none=True).keys()),
    )
    row = await session.get(Interface, interface_id)
    if row is None:
        raise AppError("ERR_CONFIG_0001", f"接口不存在：{interface_id}", http=400)

    if body.llm is not None and body.llm not in (0, 1):
        raise AppError("ERR_CONFIG_0001", f"llm 非法：{body.llm}", http=400)
    if body.body_search is not None and body.body_search not in (0, 1):
        raise AppError("ERR_CONFIG_0001", f"body_search 非法：{body.body_search}", http=400)
    if body.llm_source is not None and body.llm_source not in _ADMIN_LLM_SOURCES:
        raise AppError(
            "ERR_CONFIG_0001",
            f"llm_source 非法：{body.llm_source}（本端点只接受 {'/'.join(_ADMIN_LLM_SOURCES)}）",
            http=400,
        )

    changes: list[str] = []
    if body.llm is not None and body.llm != row.llm:
        changes.append(f"llm {row.llm}→{body.llm}")
        row.llm = body.llm
        if body.llm == 1 and row.llm_suspect:
            # 裁定 2：人工确认 llm ⇒ 疑似漏标告警解除
            changes.append(f"llm_suspect {row.llm_suspect}→0")
            row.llm_suspect = 0
    if body.body_search is not None and body.body_search != row.body_search:
        changes.append(f"body_search {row.body_search}→{body.body_search}")
        row.body_search = body.body_search
    if body.llm_source is not None and body.llm_source != row.llm_source:
        changes.append(f"llm_source {_enum_str(row.llm_source)}→{body.llm_source}")
        row.llm_source = body.llm_source

    if not changes:
        # 空改动不写审计（否则审计表被「点了但没改」的行淹掉）；仍返回当前态。
        out = _interface_out(row)
        logger.debug("admin 改接口 出参: id=%s 无字段变更，未写审计", interface_id)
        return out

    row.updated_by = user.username
    detail = f"agent_id={row.agent_id} interface={row.interface}：" + "；".join(changes)
    session.add(
        ConversionRecord(
            cluster_id=None,
            link_id=None,
            action=ACTION_INTERFACE_CHANGE,
            detail=detail[:_DETAIL_MAX],
            actor_user_id=user.id,
        )
    )
    out = _interface_out(row)  # 同上：提交前组装
    await session.commit()
    logger.info(
        "接口字典订正：id=%s %s（admin=%s）", interface_id, "；".join(changes), user.username
    )
    logger.debug("admin 改接口 出参: id=%s 变更=%s", interface_id, changes)
    return out
