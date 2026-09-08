"""ORM 基类 + MySQL 类型常量（detail §5.1：时间列一律 DATETIME(3) 存 UTC）。

时间列 default / ON UPDATE 一律交 DB 侧维护（CURRENT_TIMESTAMP(3)），ORM 不参与时间写入，
防应用与 DB 双时钟漂移。模型列据此直接引用本模块常量，保证 12 张表时间列形态一致。
"""
from sqlalchemy import text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# DATETIME(3)：MySQL fsp=3，毫秒精度。
DT3 = mysql.DATETIME(fsp=3)
# DEFAULT CURRENT_TIMESTAMP(3)
TS_DEFAULT = text("CURRENT_TIMESTAMP(3)")
# DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)（updated_ts/updated_at 专用）
TS_UPDATE = text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)")

# MySQL 无符号整形（§5.1 DDL：主键/外键/代数等均 UNSIGNED）
BIGINT_UX = mysql.BIGINT(unsigned=True)   # BIGINT UNSIGNED
TINYINT_UX = mysql.TINYINT(unsigned=True)  # TINYINT UNSIGNED（claim_k）
TINYINT = mysql.TINYINT()                  # TINYINT（signed：status/enable/开关位）
