"""worker：后台 jobs（judge_scan/cluster/assemble/claim_ttl/recheck/rollup 共 6 个，
周期常量见 main.py:35-42；detail §1.3 分布式单飞 CAS 锁；§4.3/§6/§7）。

两处易误列，勿再加回本清单：
- requeue 不在 worker —— 它由 admin/offline 请求驱动（app/backflow/requeue.py），不设周期；
- reentry 无独立 job —— 同键再现的复发归并由 cluster_job 内联（§7.5；T-3.5/2026-09-09 拍板，
  不落 reentry_job.py，独立 job 会与 cluster_job 双消费冲突）。
"""
