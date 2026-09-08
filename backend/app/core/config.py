"""应用配置：pydantic-settings 读 env（仅密钥与连接类；业务参数走 system/dict_config 表，
detail §10）。

对齐 offline 仓惯例：
- 启动强校验：jwt_secret ≥256bit、fernet_keys 非空、db_password 非空；
  测试环境（app_env=test）跳过（单测不连真库，用注入 Settings(app_env=test)）。
- 资源命名带 `{resource_env}.` 前缀（共享 infra 租户隔离，detail §3.3/§5.2/§13.3）：
  库 = `{resource_env}.obs`、topic = `{resource_env}.obs.agent.<name>` / `.selfmonitor`、
  index = `{resource_env}.obs-event-yyyyWW` 等——拼装落在调用侧，本文件只出前缀与连接串。
"""
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ---- 运行 ----
    app_env: str = "dev"       # dev / test / prod（test 跳过密钥强校验）
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    # 部署环境前缀 {env}：dev 底座 = dev；生产值域上线前与 infra 登记一致（solution §17 #15）
    resource_env: str = "dev"

    # ---- MySQL（库名带 {resource_env}. 前缀；db_name 显式则优先） ----
    # 宿主直连端口对齐共享 infra 宿主映射（infra 仓 MYSQL_PORT，默认 33061；容器内走 mysql:3306）
    db_host: str = "localhost"
    db_port: int = 33061
    db_user: str = ""
    db_name: str = ""          # 缺省 = {resource_env}.obs
    db_password: str = ""
    db_migrate_user: str = ""      # alembic DDL 专用（成对时优先，缺省回退 db_user，offline 同款）
    db_migrate_password: str = ""

    # ---- Elasticsearch 8.x（本地直连 dev；宿主端口对齐共享 infra ES_HTTP_PORT，默认 39200；
    # 容器内经 elasticsearch:9200；生产 infra 分配 endpoint 经 .env） ----
    es_url: str = "http://localhost:39200"

    # ---- Kafka（本地直连；共享 infra 宿主端口见 infra 仓 KAFKA_PORT 映射） ----
    kafka_bootstrap: str = "localhost:39092"
    kafka_consumer_group: str = ""    # 缺省 = {resource_env}.obs.consumer

    # ---- 密钥（强校验） ----
    jwt_secret: str = ""
    fernet_keys: str = ""
    jwt_access_minutes: int = 15      # §13.1：短效 access
    jwt_refresh_days: int = 7

    # ---- 引导 admin（seed.py init_admin 用，§13.1；生产首登即改密） ----
    admin_username: str = "admin"
    admin_password: str = ""

    # ---- CORS（开发期前端源；生产同源可置空不注册） ----
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @model_validator(mode="after")
    def _validate_secrets(self) -> "Settings":
        if self.app_env == "test":
            return self
        if not self.jwt_secret or len(self.jwt_secret.encode("utf-8")) < 32:
            raise ValueError("jwt_secret 必须 ≥256bit（32 字节 UTF-8），禁止启动")
        if not self.fernet_keys.strip():
            raise ValueError("fernet_keys 为空，禁止启动（MultiFernet 逗号分隔多代）")
        if not self.db_password:
            raise ValueError("db_password 为空，禁止启动")
        return self

    # ---- 派生 ----
    @property
    def database(self) -> str:
        return self.db_name or f"{self.resource_env}.obs"

    @property
    def consumer_group(self) -> str:
        return self.kafka_consumer_group or f"{self.resource_env}.obs.consumer"

    # ---- Kafka topic / ES index 命名（{resource_env}. 前缀注入，detail §3.3/§5.2） ----
    # topic 白名单正则 = ^(?:[a-z0-9-]+\.)?obs\.(?:agent\.[a-z0-9-]+|selfmonitor)$（§13.2）

    def agent_topic(self, agent_name: str) -> str:
        """agent 业务 topic：`{env}.obs.agent.<name>`，partition=1（detail §3.3）。"""
        return f"{self.resource_env}.obs.agent.{agent_name}"

    @property
    def selfmonitor_topic(self) -> str:
        """平台自监控信号 topic（detail §3.6：心跳/dropped 计数共用，与业务 topic 同 ACL）。"""
        return f"{self.resource_env}.obs.selfmonitor"

    @property
    def event_index_prefix(self) -> str:
        """事件 index 前缀（周滚动名 = 前缀 + yyyyWW，detail §5.2；WW 拼装落 ES 层）。"""
        return f"{self.resource_env}.obs-event"

    @property
    def log_index_prefix(self) -> str:
        """日志 index 前缀（周滚动名 = 前缀 + yyyyWW，detail §5.2）。"""
        return f"{self.resource_env}.obs-log"

    @property
    def sqlalchemy_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.db_user}:{self.db_password}@"
            f"{self.db_host}:{self.db_port}/{self.database}?charset=utf8mb4"
        )

    @property
    def sqlalchemy_migrate_url(self) -> str:
        """迁移专用连接：DB_MIGRATE_* 成对时用迁移账号（DDL），任一缺省回退主账号。"""
        if self.db_migrate_user and self.db_migrate_password:
            user, pw = self.db_migrate_user, self.db_migrate_password
        else:
            user, pw = self.db_user, self.db_password
        return (
            f"mysql+aiomysql://{user}:{pw}@"
            f"{self.db_host}:{self.db_port}/{self.database}?charset=utf8mb4"
        )

    @property
    def fernet_key_list(self) -> list[str]:
        return [k.strip() for k in self.fernet_keys.split(",") if k.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """取进程级单例 Settings（lru_cache）。业务代码一律走本函数，勿模块级实例化。

    不在模块顶层生成单例：import app.core.config 即触发密钥强校验会锁死测试/工具链
    （骨架测试经 conftest 设 APP_ENV=test + create_app(test_settings) 注入，见 main.py）。
    """
    return Settings()
