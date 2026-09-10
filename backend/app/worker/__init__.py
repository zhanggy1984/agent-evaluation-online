"""worker：后台 jobs（judge_scan/cluster/assemble/claim_ttl/rejudge/rollup 共 6 个，
周期常量见 main.py:34-45；detail §1.3 分布式单飞 CAS 锁；§4.3/§6/§7）。

三处易误列，勿再加回本清单：
- requeue 不在 worker —— 它由 admin/offline 请求驱动（app/backflow/requeue.py），不设周期；
- reentry 无独立 job —— 同键再现的复发归并由 cluster_job 内联（§7.5；T-3.5/2026-09-09 拍板，
  不落 reentry_job.py，独立 job 会与 cluster_job 双消费冲突）；
- **回查判定（原 recheck_job）已不是拉取型 job** —— v1.23 第 3 刀起 offline 主动推结果，判定
  在推送端点内同事务同步做（api/backflow.record_regression_result → verify.judge_link），
  原轮询链（core/offline_client + worker/recheck_job）已整删，**别把它补回来**（补判由
  rejudge_job 承担，见下方 ★；两者名字像、机制相反，最易混）。

★ **rejudge_job 是 6 个 job 里的一员，与已删的 recheck 不是一回事**（本批补，(a)）：
  - recheck（已删）= online **主动拉** offline 结果的 60s outbound 轮询；
  - rejudge（新）= **纯本地**扫描 `status=='claim' ∧ 有现行 pending link` 的簇，重放本 link
    已落库的结果行补判一次，**零 outbound**（不 import 任何 offline 客户端）。
  为什么需要：判定触发已从「无限重试轮询」退化为「推送到达时一次性事件」，三类「事件到达时
  未就绪」现场（① claim 晚于推送 ② 判定抛异常被降级 ③ 状态过渡窗口）此后再无事件驱动 ——
  没有本 job，link 会永久停在 pending。详见 rejudge_job 模块 docstring。
  **故 job 数 = 6，勿因「recheck 已删」把它改回 5。**
"""
