"""converter/envelope + no_fallback_cfg 纯逻辑 + worker/main assemble loop（P2-2 / T-3.2）。

组装 DB 壳（扫批 open-无现行 link → 每候选 link+conv 事务 / uk_link_current 吸收 /
dict_config 真库读）留集成探针（仿 cluster「DB 壳留集成探针」先例）：
tests/integration/assemble_probe.py 容器内 `docker exec obs-backend` 跑真库断言。
本文件测：
- converter/envelope：parse_snapshot_input 嵌入规则、build_envelope 逐键（§7.1 sample）、
  fix_version 即时值 / 空词表 fail-closed、assemble_cluster 编排（词表命中产物）；
- converter/no_fallback_cfg：resolve_fallback_wordlist 命中/缺配置/缺 agent 三态；
- worker/main：_assemble_loop 单 job 异常自愈 + _stop 取消（monkeypatch run_assemble）。
真 MySQL/ES 链不连。
"""
import asyncio
import json
import re

import pytest
from _fakes import FakeAsyncSession, ns

import app.worker.main as worker_main
from app.converter.envelope import (
    assemble_cluster,
    build_envelope,
    parse_snapshot_input,
)
from app.converter.no_fallback_cfg import parse_words, resolve_fallback_wordlist
from app.models.agent import Agent
from app.models.config import DictConfig
from app.models.error_flow import ConversionRecord, ErrorCaseLink

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _cluster(**over):
    base = dict(
        id=10, agent="good-question", interface="POST /api/chat/{id}",
        first_trace_id="tr-9f2c1a", generation=1, trigger_version="2026.08.31-r47",
        fix_version=None, input_snapshot='{"question": "帮我查一下XX政策"}',
        input_truncated=0, error_type="llm_timeout",
    )
    return ns(**{**base, **over})


def _session(*, words=None, version=7, has_agent=True):
    rows = {}
    if has_agent:
        rows[Agent] = [ns(id=1, name="good-question")]
    if words is not None:
        rows[DictConfig] = [ns(agent_id=1, config_key="fallback_utterance",
                               config_value=words, version=version)]
    return FakeAsyncSession(registry=rows)


# ---- parse_snapshot_input：evidence.input 嵌入规则 ---------------------------------

class TestParseSnapshotInput:
    def test_dict_snapshot_restored(self):
        snap = json.dumps({"question": "帮我查一下XX政策", "session_id": "{id}"},
                          ensure_ascii=False)
        assert parse_snapshot_input(snap) == {
            "question": "帮我查一下XX政策", "session_id": "{id}"}

    def test_list_snapshot_restored(self):
        assert parse_snapshot_input('[1, "a"]') == [1, "a"]

    def test_plain_str_snapshot_passthrough(self):
        # str 原始 input 存明文（非 JSON 文本）→ 原样嵌入
        assert parse_snapshot_input("帮我查一下XX政策") == "帮我查一下XX政策"

    def test_empty_or_none_returns_none(self):
        assert parse_snapshot_input(None) is None
        assert parse_snapshot_input("") is None


# ---- build_envelope：§7.1 sample 逐键 -------------------------------------------------

class TestBuildEnvelope:
    def test_field_mapping(self):
        env = build_envelope(
            cluster=_cluster(),
            words=["抱歉，暂时无法回答", "系统繁忙，请稍后再试", "当前功能维护中"],
            wordlist_version=7,
        )
        assert env["schema_version"] == "1.0"
        assert env["case_type"] == "regression_error"
        assert UUID_RE.match(env["payload_id"])
        # source 溯源（cluster_id 溯源可空，本批组装即填）
        assert env["source"] == {
            "agent": "good-question", "interface": "POST /api/chat/{id}",
            "trace_id": "tr-9f2c1a", "cluster_id": 10, "generation": 1,
        }
        assert env["versions"] == {"trigger_version": "2026.08.31-r47", "fix_version": None}
        assert env["evidence"]["input"] == {"question": "帮我查一下XX政策"}
        assert env["evidence"]["output"] is None  # body 采集默认关恒 null
        assert env["evidence"]["session_snapshot"] is None
        assert env["evidence"]["retrieve_hit"] is None
        assert env["assert"] == {
            "no_fallback": {"rule": "wordlist", "config_ref": {"wordlist_version": 7}}}
        assert env["no_fallback_config"] == {
            "words": ["抱歉，暂时无法回答", "系统繁忙，请稍后再试", "当前功能维护中"],
            "wordlist_version": 7}
        # assert.config_ref === no_fallback_config.wordlist_version（同刻同源）
        assert (env["assert"]["no_fallback"]["config_ref"]["wordlist_version"]
                == env["no_fallback_config"]["wordlist_version"])
        # 整体可 json 序列化且中文直存（payload_json = ensure_ascii=False）
        dumped = json.dumps(env, ensure_ascii=False)
        assert "帮我查一下XX政策" in dumped
        assert json.loads(dumped)["payload_id"] == env["payload_id"]

    def test_fix_version_taken_at_assemble(self):
        assert build_envelope(cluster=_cluster(), words=[], wordlist_version=0)[
            "versions"]["fix_version"] is None
        env = build_envelope(cluster=_cluster(fix_version="2026.09.05-r2"),
                             words=[], wordlist_version=0)
        assert env["versions"]["fix_version"] == "2026.09.05-r2"  # 组装即时值

    def test_empty_wordlist_fail_closed_marker(self):
        # 空词表/配置缺 → 信封照建 words=[] + version 兜底（offline 结构自检 content_gap）
        env = build_envelope(cluster=_cluster(), words=[], wordlist_version=0)
        assert env["no_fallback_config"] == {"words": [], "wordlist_version": 0}
        assert env["assert"]["no_fallback"]["config_ref"]["wordlist_version"] == 0

    def test_snapshot_missing_yields_null_input(self):
        env = build_envelope(cluster=_cluster(input_snapshot=None), words=[], wordlist_version=0)
        assert env["evidence"]["input"] is None


# ---- resolve_fallback_wordlist：dict_config 读（fake session 等值语义） ----------------

class TestResolveFallbackWordlist:
    async def _resolve(self, session, name="good-question"):
        return await resolve_fallback_wordlist(session, agent_name=name)

    @pytest.mark.asyncio
    async def test_hit_returns_words_and_version(self):
        session = _session(words=["抱歉，暂时无法回答"], version=7)
        words, version = await self._resolve(session)
        assert words == ["抱歉，暂时无法回答"] and version == 7

    @pytest.mark.asyncio
    async def test_missing_config_yields_empty(self):
        session = _session()  # 有 agent 无 fallback_utterance 行 → (words=[], 0)
        assert await self._resolve(session) == ([], 0)

    @pytest.mark.asyncio
    async def test_missing_agent_yields_empty(self):
        session = _session(has_agent=False, words=["x"])
        assert await self._resolve(session) == ([], 0)

    def test_parse_words_defensive(self):
        assert parse_words(["a"]) == ["a"]
        assert parse_words(None) == []
        assert parse_words("not-a-list") == []


# ---- assemble_cluster：编排产物（link + conv）-----------------------------------------

class TestAssembleCluster:
    @pytest.mark.asyncio
    async def test_success_builds_link_and_conv(self):
        session = _session(words=["抱歉，暂时无法回答"], version=7)
        ok = await assemble_cluster(session, _cluster())
        assert ok is True
        added = session.added
        assert len(added) == 2
        link, conv = added
        assert isinstance(link, ErrorCaseLink)
        assert isinstance(conv, ConversionRecord)
        assert link.cluster_id == 10
        assert link.source_trace_id == "tr-9f2c1a"
        assert link.trigger_version == "2026.08.31-r47"
        assert link.fix_version is None
        assert link.input_truncated == 0
        env = json.loads(link.payload_json)
        assert env["payload_id"] == link.payload_id
        assert UUID_RE.match(link.payload_id)
        assert env["evidence"]["input"] == {"question": "帮我查一下XX政策"}
        assert env["no_fallback_config"]["words"] == ["抱歉，暂时无法回答"]
        assert conv.action == "assemble"
        assert conv.cluster_id == 10
        assert conv.actor_user_id is None
        assert link.payload_id in conv.detail

    @pytest.mark.asyncio
    async def test_empty_wordlist_still_builds(self):
        # 空表照建（fail-closed 载体 words==[]，offline 自检判不过）
        session = _session(words=[], version=1)
        ok = await assemble_cluster(session, _cluster())
        assert ok is True
        link = session.added[0]
        env = json.loads(link.payload_json)
        assert env["no_fallback_config"] == {"words": [], "wordlist_version": 1}

    @pytest.mark.asyncio
    async def test_missing_snapshot_skips(self):
        # E-13：快照缺 input 实文 → 只计数不组装（不建 link 不写 conv）
        session = _session(words=["a"], version=1)
        ok = await assemble_cluster(session, _cluster(input_snapshot=None))
        assert ok is False and session.added == []

    @pytest.mark.asyncio
    async def test_missing_config_fail_closed(self):
        session = _session()  # 有 agent、无配置行 → version=0 兜底
        ok = await assemble_cluster(session, _cluster())
        assert ok is True
        env = json.loads(session.added[0].payload_json)
        assert env["no_fallback_config"]["wordlist_version"] == 0
        assert env["no_fallback_config"]["words"] == []


# ---- worker/main：_assemble_loop 生命周期（monkeypatch job 函数，不连库） ---------------

class TestAssembleLoop:
    @pytest.mark.asyncio
    async def test_runs_until_stop_and_self_heals(self, monkeypatch):
        calls: list[int] = []

        async def fake_run_assemble(engine, *, logger, batch):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("DB 抖动模拟")  # 首轮异常 → 下轮自愈
            return 0

        monkeypatch.setattr(worker_main, "run_assemble", fake_run_assemble)
        monkeypatch.setattr(worker_main, "ASSEMBLE_INTERVAL_S", 0)

        app = worker_main.WorkerApp(worker_main.get_settings())

        async def stopper():
            while len(calls) < 3:
                await asyncio.sleep(0)
            app._stop.set()

        await asyncio.gather(app._assemble_loop(), stopper())
        assert len(calls) >= 3  # 异常轮不退出，正常轮继续直到 stop

    @pytest.mark.asyncio
    async def test_cancel_stops_cleanly(self, monkeypatch):
        async def fake_run_assemble(engine, *, logger, batch):
            await asyncio.sleep(3600)

        monkeypatch.setattr(worker_main, "run_assemble", fake_run_assemble)
        app = worker_main.WorkerApp(worker_main.get_settings())
        task = asyncio.create_task(app._assemble_loop())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
