"""API 端点测试替身（auth/trace）：不连真 MySQL/ES。

- FakeAsyncSession：SQLAlchemy 表达式树的**最小等值解析**——只理解 auth/trace 用到的
  `select(Model).where(col == val, ...)` / `session.get(Model, pk)` 形态；条件不匹配或
  表达式结构超出白名单即按无行处理（宁可漏测不假装支持任意 SQL）。
- FakeES：录调用的 ES 查询 client（search 回 canned、options 记超时）。
- FakeResult：`scalar_one_or_none()` 语义。
"""
from types import SimpleNamespace

from app.models.user import User as _User
from app.models.user import UserSession as _UserSession


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
    """行为最小集：execute(等值 select) / get / add / commit。

    rows 用 SimpleNamespace 而非 ORM 实例：端点只读属性 + 改 revoked_at，
    不需走 ORM 生命周期/类型转换。
    """

    def __init__(self, *, users=(), sessions=()):
        self.users = list(users)
        self.sessions = list(sessions)
        self.added: list = []
        self.commits = 0

    async def get(self, model, pk):
        if model is _User:
            return next((r for r in self.users if r.id == pk), None)
        if model is _UserSession:
            return next((r for r in self.sessions if r.id == pk), None)
        return None

    async def execute(self, stmt, params=None, execution_options=None):
        desc = stmt.column_descriptions
        entity = desc[0]["entity"] if desc else None
        conds = _eq_conds(stmt.whereclause)
        if entity is _User:
            rows = self.users
        elif entity is _UserSession:
            rows = self.sessions
        else:
            return FakeResult(None)
        for row in rows:
            if all(getattr(row, k, None) == v for k, v in conds.items()):
                return FakeResult(row)
        return FakeResult(None)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


def ns(**kw):
    return SimpleNamespace(**kw)


class FakeES:
    """录调用的 ES 查询 client：search 返回 canned、options 记录 request_timeout。"""

    def __init__(self, response=None, exc=None):
        self._resp = response
        self._exc = exc
        self.calls: list = []
        self.timeouts: list = []

    def options(self, **kw):
        self.timeouts.append(kw.get("request_timeout"))
        return self

    async def search(self, index=None, body=None):
        self.calls.append((index, body))
        if self._exc is not None:
            raise self._exc
        return self._resp


def es_hits(total, sources):
    return {
        "hits": {
            "total": {"value": total, "relation": "eq"},
            "hits": [{"_source": s} for s in sources],
        }
    }
