"""admin 系统管理面（detail §8.6）：配置管理 + 用户管理。全部端点 `AdminUser` 依赖。

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
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser
from app.api.schemas import (
    ConfigItem,
    ConfigUpdateRequest,
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
from app.models.agent import Agent
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
