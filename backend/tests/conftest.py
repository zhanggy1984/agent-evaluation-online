"""测试共享 fixture：注入 Settings(app_env=test) 跳过密钥强校验，起无中间件依赖的 app。

骨架期测试不连 MySQL/ES/Kafka（依赖连通冒烟归 #71 / T-0.6）。
"""
import os

import pytest

# 必须在 import 任何 app 模块之前设置：main.py 模块级 `app = create_app()` 与 config
# 在 import 时即求值，APP_ENV=test 使其跳过密钥强校验（无 .env 也能跑骨架单测）。
os.environ["APP_ENV"] = "test"
os.environ["RESOURCE_ENV"] = "dev"


@pytest.fixture
def test_settings():
    # app.* 延迟到 fixture 内 import：env 已就位（规避 E402，也让 F821 不误报注解）
    from app.core.config import Settings

    return Settings(app_env="test")


@pytest.fixture
def client(test_settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app(test_settings)
    with TestClient(app) as c:
        yield c
