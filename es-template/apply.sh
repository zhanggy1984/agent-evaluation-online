#!/usr/bin/env bash
# 幂等应用 obs ES index template + ILM policy（平台提交 → infra/本地落建，§7.1 索引治理）。
# 用法：ENV=dev [ES_URL=http://localhost:39200] bash apply.sh
# 可重复执行（PUT 幂等覆盖）；template body 内 ${ENV} 以 sed 注入（不依赖 envsubst）。
set -euo pipefail

ENV="${ENV:?需设置 ENV（如 dev）}"
ES_URL="${ES_URL:-http://localhost:39200}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CT='Content-Type: application/json'

echo "[1/3] PUT ILM policy obs-ilm-30d"
curl -fsS -X PUT "$ES_URL/_ilm/policy/obs-ilm-30d" -H "$CT" \
  -d @"$DIR/obs-ilm-policy.json" >/dev/null

for tpl in obs-event-template obs-log-template; do
  echo "[*] PUT index template $tpl (env=$ENV)"
  sed "s/\${ENV}/$ENV/g" "$DIR/$tpl.json" \
    | curl -fsS -X PUT "$ES_URL/_index_template/$tpl" -H "$CT" -d @- >/dev/null
done

echo "[verify] ILM:"
curl -fsS "$ES_URL/_ilm/policy/obs-ilm-30d" | head -c 200; echo
echo "[verify] templates:"
curl -fsS "$ES_URL/_index_template/obs-event-template" | head -c 400; echo
echo "OK: obs template/ILM 已就绪（env=$ENV）。"
