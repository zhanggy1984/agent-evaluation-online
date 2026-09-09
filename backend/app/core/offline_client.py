"""offline 只读回查 client（§8.7 online→offline 读面，P2-4 E-7 recheck 判定数据源）。

- 三读面：runs（agent+version+终态 status 过滤，含 excluded_case_ids + na error_type
  明细）、run_results（per-case pass_fail + error_type）、agent_versions（R-17 K 序列
  版本锚 = 发版拓扑权威）。
- 认证：Bearer evaluator_service_secret（复用平台预共享凭证，§13.5 双向认证；offline
  配套轨落地后同值）。
- 连续失败指数退避重试；超上限抛 OfflineReadError → recheck_job 捕获 → 聚类详情提示
  「回查失败待人工」（§16，online 不退避无限）。
- runs item 契约（本批钉定，real offline 阶段 4 对齐）：{run_id, status, ended_ts?,
  excluded_case_ids[], na_error_types[]}——na_error_types = 该 run 内 na 行 error_type
  去重明细（online 按 §7.6 v1.5 R-2 影响域归类判纯净）。
"""
import asyncio
from typing import Any

import httpx

from app.core.log import get_logger

logger = get_logger("app.core.offline_client")

# recheck 只消费的 run 终态（§7.6：绝不含 running/pending，防 premature fixed）
RUN_TERMINAL_STATUSES = ("completed", "partial_failed", "timeout", "cancelled")
_REQUEST_TIMEOUT_S = 10
_RETRY_MAX = 3          # 连续失败重试上限（§16 超上限 → 回查失败待人工）
_RETRY_BASE_S = 1.0     # 指数退避底窗（1s/2s 后放弃）


class OfflineReadError(Exception):
    """offline 读面不可达/契约异常（语义错误码缺省 500 由调用方兜，见 recheck_job）。"""


class OfflineClient:
    """offline 只读面 client。transport 可注入（探针假 offline 环 1）。"""

    def __init__(
        self,
        base_url: str,
        *,
        secret: str,
        timeout_s: float = _REQUEST_TIMEOUT_S,
        transport: Any | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout_s,
            trust_env=False,  # 不回退环境代理（容器内直连）
            transport=transport,
            headers={"Authorization": f"Bearer {secret}"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: list[tuple[str, str]] | dict | None = None) -> dict:
        """GET + 指数退避重试；HTTP/网络异常超上限 → OfflineReadError（§16）。"""
        for attempt in range(_RETRY_MAX):
            try:
                resp = await self._client.get(path, params=params)
                if resp.status_code >= 400:
                    raise OfflineReadError(
                        f"offline 读面 HTTP {resp.status_code}: {path}（可能版本不匹配）"
                    )
                return resp.json()
            except httpx.HTTPError as exc:
                if attempt >= _RETRY_MAX - 1:
                    raise OfflineReadError(f"offline 读面不可达: {path}") from exc
                await asyncio.sleep(_RETRY_BASE_S * (2 ** attempt))
        raise OfflineReadError(f"offline 读面重试耗尽: {path}")

    async def list_runs(
        self,
        *,
        agent: str,
        version: str | None = None,
        case_id: str | None = None,
        statuses: tuple[str, ...] = RUN_TERMINAL_STATUSES,
    ) -> list[dict]:
        """GET runs?agent=&version=&status=&case_id=（§8.7；status 取值集 = 终态白名单）。"""
        params: list[tuple[str, str]] = [("agent", agent)]
        if version:
            params.append(("version", version))
        if case_id:
            params.append(("case_id", case_id))
        for s in statuses:
            params.append(("status", s))
        body = await self._get("/api/v1/runs", params)
        runs = body.get("runs")
        return runs if isinstance(runs, list) else []

    async def run_results(self, run_id: str, *, case_id: str | None = None) -> list[dict]:
        """GET runs/{id}/results?case_id=（per-case pass_fail + error_type，§8.7）。"""
        params = {"case_id": case_id} if case_id else None
        body = await self._get(f"/api/v1/runs/{run_id}/results", params)
        rows = body.get("rows", body.get("results"))
        return rows if isinstance(rows, list) else []

    async def agent_versions(self, *, agent: str, window_days: int = 14) -> list[dict]:
        """GET agents/{agent}/versions（R-17 K 序列版本锚；window 默认覆盖 claim TTL 14d）。"""
        body = await self._get(f"/api/v1/agents/{agent}/versions", {"window_days": window_days})
        versions = body.get("versions")
        return versions if isinstance(versions, list) else []
