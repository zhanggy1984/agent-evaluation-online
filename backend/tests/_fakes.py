"""API 端点测试替身（auth/trace）：不连真 MySQL/ES。

- FakeAsyncSession：SQLAlchemy 表达式树的**最小等值解析**——只理解 auth/trace 用到的
  `select(Model).where(col == val, ...)` / `session.get(Model, pk)` 形态；条件不匹配或
  表达式结构超出白名单即按无行处理（宁可漏测不假装支持任意 SQL）。
- FakeES：录调用的 ES 查询 client（search 回 canned、options 记超时）。
- FakeResult：`scalar_one_or_none()` 语义。
"""
from types import SimpleNamespace

from app.models.agent import Agent, Interface
from app.models.config import DictConfig
from app.models.error_flow import TraceJudgeState
from app.models.user import User as _User
from app.models.user import UserSession as _UserSession


class _NullSavepoint:
    """`session.begin_nested()` 替身：no-op savepoint（不回退、不模拟异常后的清理）。

    FakeAsyncSession 只做 SQLAlchemy 表达式树的**最小等值解析**、不真写库，故「回退到
    savepoint」在替身上无物可回退；单测只验「判定段确实被 savepoint 包住」的接线。
    真回退语义（DB 异常后行仍在）由 push_probe 真库场景覆盖。
    """

    async def __aenter__(self):
        return None

    async def __aexit__(self, *exc):
        return False


class FakeResult:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row

    def scalar(self):
        return self._row


def _eq_conds(whereclause):
    """提取 AND 等值条件 {列key: 值}（auth 查询全是这种形态）。"""
    from sqlalchemy.sql.elements import BinaryExpression, BooleanClauseList
    from sqlalchemy.sql.operators import eq

    out: dict = {}

    def rec(node):
        if node is None:
            return
        if isinstance(node, BooleanClauseList):  # and_(a, b)
            for child in node.get_children():
                rec(child)
        elif isinstance(node, BinaryExpression) and node.operator is eq:
            key = getattr(node.left, "key", None) or getattr(node.left, "name", None)
            right = node.right
            if isinstance(right, (str, int, float, bool)) or right is None:
                val = right
            else:  # BindParameter / 其他 ClauseElement：取 .value
                val = getattr(right, "value", None)
            if key is not None:
                out[key] = val
        # 非等值谓词（like/range/is 等）：本批未用，忽略

    rec(whereclause)
    return out


class FakeAsyncSession:
    """行为最小集：execute/scalar(等值 select) / get / add / commit / flush。

    rows 用 SimpleNamespace 而非 ORM 实例：端点只读属性 + 改标记位/JSON 字段，
    不需走 ORM 生命周期/类型转换。

    entity 行注册两种方式：
    - auth/trace 端点：users=/sessions= 专属 kwargs（模型白名单 _User/_UserSession）；
    - 判定/扫描（analyzer/consumer/worker）：`registry={Model: [rows]}` 按 ORM 模型注入
      Agent/Interface/DictConfig/TraceJudgeState 等。列级 select（select(Model.col)）
      经 expr.table 反查模型 → 返回匹配行的该列属性。
    """

    def __init__(self, *, users=(), sessions=(), registry=None):
        self.users = list(users)
        self.sessions = list(sessions)
        self.registry: dict = dict(registry or {})
        self.added: list = []
        self.commits = 0

    # ---- entity / 行解析 -------------------------------------------------

    def _rows_for(self, entity):
        if entity is _User:
            return self.users
        if entity is _UserSession:
            return self.sessions
        return self.registry.get(entity, [])

    @staticmethod
    def _resolve_entity(stmt):
        """select 目标 → 模型类：整实体直取；列级 select 经 expr.table 反查。"""
        desc = stmt.column_descriptions[0]
        entity = desc.get("entity")
        if entity is not None:
            return entity
        table = getattr(desc.get("expr"), "table", None)
        if table is not None:
            for model in (Agent, Interface, DictConfig, TraceJudgeState):
                if model.__table__ is table:
                    return model
        return None

    @staticmethod
    def _return_value(stmt, row, entity):
        """整实体 select 返回行；列级 select 返回该列属性（config_value/id…）。

        判别看 expr：列级 select 的 expr 是 InstrumentedAttribute（带列名），整实体
        select 是实体表达式——SQLAlchemy 2.0 两种 select 的 column_descriptions 都带
        entity，不能以 entity 判别（探测定型：config_value 列 select entity=DictConfig）。
        """
        from sqlalchemy.orm.attributes import InstrumentedAttribute

        desc = stmt.column_descriptions[0]
        if isinstance(desc.get("expr"), InstrumentedAttribute):
            return getattr(row, desc.get("name"), None)
        return row

    def _match(self, entity, conds):
        for row in self._rows_for(entity):
            if all(getattr(row, k, None) == v for k, v in conds.items()):
                return row
        return None

    # ---- SQLAlchemy 异步会话面 -------------------------------------------

    async def get(self, model, pk):
        if model is _User:
            return next((r for r in self.users if r.id == pk), None)
        if model is _UserSession:
            return next((r for r in self.sessions if r.id == pk), None)
        return None

    async def execute(self, stmt, params=None, execution_options=None):
        entity = self._resolve_entity(stmt) if stmt is not None else None
        if entity is None:
            return FakeResult(None)
        conds = _eq_conds(stmt.whereclause)
        row = self._match(entity, conds)
        return FakeResult(row)

    async def scalar(self, stmt, params=None):
        """与 execute 同匹配逻辑，返回匹配行/该列属性（state/worker 用 session.scalar）。"""
        entity = self._resolve_entity(stmt) if stmt is not None else None
        if entity is None:
            return None
        conds = _eq_conds(stmt.whereclause)
        row = self._match(entity, conds)
        if row is None:
            return None
        return self._return_value(stmt, row, entity)

    async def flush(self):
        pass

    def begin_nested(self):
        return _NullSavepoint()

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


def ns(**kw):
    return SimpleNamespace(**kw)


class FakeRows:
    """`.all()` 语义的成批行结果（GROUP BY 计数等；FakeResult 只有单行语义）。"""

    def __init__(self, items):
        self._items = list(items)

    def all(self):
        return self._items


def requeue_count_link_ids(stmt) -> list[int] | None:
    """识别 R-7 的「按 link_id IN (…) 分组计 action=requeue 行数」查询 → 返回 in 列表。

    非该形态返回 None（stub 据此让其它分支继续判）。识别依据 = whereclause 里同时有
    `ConversionRecord.link_id IN (字面量列表)` 与 `action == 'requeue'` 等值条件——不解释
    SQL，只够 stub 真按行聚合出计数（口径与真库实现一致：只数 requeue 行、按 link 分组）。
    """
    from sqlalchemy.sql.elements import BinaryExpression, BooleanClauseList
    from sqlalchemy.sql.operators import eq, in_op

    wc = getattr(stmt, "whereclause", None)
    if wc is None or not isinstance(wc, BooleanClauseList):
        return None
    ids = None
    has_action = False
    for node in wc.get_children():
        if not isinstance(node, BinaryExpression):
            continue
        key = getattr(node.left, "key", None)
        if node.operator is in_op and key == "link_id":
            value = getattr(node.right, "value", None)
            if isinstance(value, (list, tuple)):
                ids = [int(v) for v in value]
        elif node.operator is eq and key == "action" and node.right.value == "requeue":
            has_action = True
    return ids if (ids is not None and has_action) else None


def aggregate_requeue_counts(conv_rows, link_ids) -> list[tuple[int, int]]:
    """按注册的 conversion_record 行真算计数 → [(link_id, count)]（stub 版 GROUP BY）。

    只数 action='requeue' ∧ link_id ∈ link_ids 的行——与 requeue.py 的 SQL 过滤同义，
    故「造 N 条 → 断言 N」测的是真实口径而非 canned 值。
    """
    from collections import Counter

    wanted = set(link_ids)
    hit = Counter(
        row.link_id for row in conv_rows
        if getattr(row, "action", None) == "requeue"
        and getattr(row, "link_id", None) in wanted
    )
    return sorted(hit.items())


class FakeES:
    """录调用的 ES 查询 client：search 返回 canned、options 记录 request_timeout。

    responses（可选）：多端点按序消费（如 llm-failures Q1→Q2 两次 search）；缺省单 response。
    """

    def __init__(self, response=None, exc=None, responses=None):
        self._resp = response
        self._exc = exc
        self._queue = list(responses or [])
        self.calls: list = []
        self.timeouts: list = []

    def options(self, **kw):
        self.timeouts.append(kw.get("request_timeout"))
        return self

    async def search(self, index=None, body=None):
        self.calls.append((index, body))
        if self._exc is not None:
            raise self._exc
        if self._queue:
            return self._queue.pop(0)
        return self._resp


def es_hits(total, sources):
    return {
        "hits": {
            "total": {"value": total, "relation": "eq"},
            "hits": [{"_source": s} for s in sources],
        }
    }
