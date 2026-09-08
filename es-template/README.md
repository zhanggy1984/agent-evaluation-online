# es-template —— obs ES index template / ILM 平台提交物

**平台提交、infra 落建**（detail §5.2 mapping / §7.1 索引治理 / §13.3）：本目录是 online 仓侧产出的「提交物」（policy + template body + 幂等应用脚本），交付给 infra 侧在目标 ES 上生效。

## 权威源与防漂移（重要）

- **mapping 唯一权威源 = `backend/app/consumer/es.py::_MAPPING`**。`obs-event-template.json` / `obs-log-template.json` 的 `mappings` 段与其**同构快照**（含 `analyzer: zh` = ik_max_word）。
- **ILM 保留口径** = detail §7.1（30d delete）。
- 两处 body 由同一权威源派生；任何 mapping 变更须**同步**：es.py `_MAPPING` → 本目录两个 template → infra 仓 `init/es/`。防漂移手段：两侧文件头注释互引本 README；变更时以 `grep analyzer` 收口核对。
- `{env}` 前缀不在文件内写死：body 用 `${ENV}` 占位，apply 时注入（索引名 `{env}.obs-event-yyyyWW` / `{env}.obs-log-yyyyWW` 前缀段来自部署 env）。

## 文件

| 文件 | 内容 |
|---|---|
| `obs-ilm-policy.json` | ILM policy `obs-ilm-30d`：hot → 30d delete |
| `obs-event-template.json` | composable index template（`${ENV}.obs-event-*`），settings 挂 ILM + zh analyzer，mapping 同构 es.py |
| `obs-log-template.json` | 同构（`${ENV}.obs-log-*`） |
| `apply.sh` | 幂等应用脚本：PUT ILM policy + 两个 template + 验证输出 |

## 用法

```bash
ENV=dev bash apply.sh                          # 默认 http://localhost:39200
ENV=prod ES_URL=http://es.example:9200 bash apply.sh
```

可重复执行（PUT 幂等覆盖）；已建 index 不受 template 变更影响（只接管**新** index，template 生效需写入到不存在 index 时触发 auto-create）。

## 关联

- **infra 仓落点**：`../infra/init/es/`（ES 启动一次性 init 服务挂载同构 body + apply 逻辑，新环境自动生效）——见 infra 仓 `docker-compose.yml` 的 `es-init` service。
- **写入路径**：consumer `dispatch_event` 不显式建 index（`es.py` docstring），生产由本 template 接管建 index；dev lifespan 守卫用升级后同构 `_MAPPING` 兜底。
