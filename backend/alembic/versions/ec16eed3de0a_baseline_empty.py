"""baseline empty — 空基线迁移锚（T-0.5 挂入）。

上游锚（down_revision=None）。初始为空的唯一目的：让 `alembic upgrade head` 有
可解析的 head（空 versions 会报 "Can't locate revision 'head'"），CI migrate 冒烟 /
T-0.6 seed 依赖它。真实表结构随各阶段 model 定义落 autogenerate 迁移，逐级链到本锚。
"""
# revision identifiers, used by Alembic.
from typing import Sequence, Union

revision: str = "ec16eed3de0a"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
