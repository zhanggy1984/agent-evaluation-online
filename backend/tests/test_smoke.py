"""骨架冒烟：config 资源前缀拼装 + health 路由 + 统一错误体。

T-0.3 验证目标的最小可测面；各业务模块单测随阶段推进补（§14）。
"""
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import AppError


def test_config_resource_prefix_default() -> None:
    """资源命名带 {resource_env}. 前缀（共享 infra 租户隔离，detail §13.3）。"""
    s = Settings(app_env="test")
    assert s.database == "dev.obs"
    assert s.consumer_group == "dev.obs.consumer"
    assert "mysql+aiomysql" in s.sqlalchemy_url


def test_config_resource_prefix_override() -> None:
    """db_name 显式优先于 {resource_env}.obs 派生。"""
    s = Settings(app_env="test", resource_env="prod", db_name="reporting")
    assert s.database == "reporting"
    assert s.consumer_group == "prod.obs.consumer"


def test_health(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_app_error_shape() -> None:
    """AppError 携带统一错误码与 HTTP 状态（§8.9 错误体 {code, message}）。"""
    err = AppError(code="ERR_SMOKE_1", detail="骨架错误体冒烟", http=422)
    assert err.code == "ERR_SMOKE_1"
    assert err.http == 422
