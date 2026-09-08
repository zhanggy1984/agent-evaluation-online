"""worker 进程入口：`python -m app.worker`（compose worker service 命令，同 backend 镜像）。

生命周期 = worker/main.main()：start（DB 守卫 + 双 job 循环）→ 等信号 → stop。
"""
import asyncio

from app.worker.main import main

if __name__ == "__main__":
    asyncio.run(main())
