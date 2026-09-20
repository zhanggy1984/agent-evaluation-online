<script setup lang="ts">
// 回流看板列表页（P2-6 T-3.7 / detail §9.2，一级菜单"错误闭环"——P1-7① 改名）：
// 总览卡 + 筛选 + cluster 表。模块本名仍是 backflow/回流，只有菜单与按钮文案改了。
// viewer/admin 均可见；二期（弃留墙/quality）在本页零入口（纯未渲染，detail §9.1 注记）。
// 时间戳 = 后端 _iso naive-UTC 字符串 → fmtISO；写面动作放详情页，本页静态 + 手动刷新。
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError } from '../api/client'
import { backflowClusters, backflowOverview } from '../api/backflow'
import { metricsInterfaces } from '../api/metrics'
import type {
  BackflowByAgent,
  BackflowCluster,
  BackflowOverview,
  BackflowQuery,
} from '../api/types'
import { agentDisplay, useAgents } from '../composables/useAgents'
import {
  BACKFLOW_INTRO,
  CLUSTER_STATUS_LABEL,
  LAYER_OPTIONS,
  STATUS_OPTIONS,
  taskState,
  TERM,
  VERIFY_STATUS_TEXT,
  WATCH_OPTIONS,
} from '../backflowLabels'
// 批 33：`fmtISO` 已随「首现 / 最新」列一并移除（本页不再渲染任何时间戳）。

const router = useRouter()

const overview = ref<BackflowOverview | null>(null)
const overErr = ref('')
const loading = ref(false)
const errorMsg = ref('')
const items = ref<BackflowCluster[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20

const queryForm = ref({ agent: '', interface: '', layer: '', status: '', watch: '' })
const { agents, loading: agentsLoading, errorMsg: agentsError, load: loadAgents } = useAgents()
// interface 筛选下拉数据源 = /metrics/interfaces 近 7d 实测接口并集（agent 无关的全局并）
const ifaces = ref<string[]>([])
const ifacesLoading = ref(false)

const maxPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

// 批 33 删除：`fmtTs` 的**唯一调用点**是已删的「首现 / 最新」列。
// 一并删掉而不是留着——留一个没人调的函数，后人会读成「某处还在用它」。

function statusLabel(s: string): string {
  return CLUSTER_STATUS_LABEL[s] ?? s
}

function statusCls(s: string): string {
  return `st-${s}`
}

// 批 29 移除 `linkOffline`（原供页脚「现行 link」用）：那处取 items[0] 冒充全局，
// 已连句删掉；表内改用下面这套**短标签**（长句版 OFFLINE_STATUS_TEXT 仍由详情页用）。

// 短标签（卡片 + 表格列用）= **直接复用筛选下拉的选项文案**。
// 改前卡片 2 渲染的是 `{{ k }}` = 后端裸键（`assembled` / `invalidated`…），
// 而同一组值在筛选下拉里是中文 ⇒ 同一页同一组值两套写法，新手无法对上号。
// 复用同一份 map 是唯一能保证「选了什么、看到的就是什么」的写法。
const OFFLINE_SHORT: Record<string, string> = Object.fromEntries(
  WATCH_OPTIONS.filter((o) => o.value).map((o) => [o.value, o.label]),
)

/** 卡片/表格列用的 offline 态短文案（未知值兜底原文，防后端加值后前端静默空白）。 */
function offlineShort(s: string | null | undefined): string {
  return s ? (OFFLINE_SHORT[s] ?? s) : '-'
}

/** 回归验证态短文案（概览卡用）。文案源 = VERIFY_STATUS_TEXT，与详情页同一份。 */
function verifyShort(s: string): string {
  return VERIFY_STATUS_TEXT[s] ?? s
}

/** 「回归验证结果」卡要渲染的行：**值为 0 的不可达态不占位**。
 *  ⚠️ 只对 `invalidated` 生效，且**只在值为 0 时**过滤 —— 这不是「前端硬编码一个永不显示的行」，
 *  而是「一个当前不可达的值不占版面」。取证（2026-09-20）：全仓唯一写 `verify_status` 的函数是
 *  `claim.py::_mark_pending_links`，4 个调用点传的值只有 superseded / passed / failed
 *  （claim.py:158/255、batches.py:153、verify.py:411/415/425），**无一处写 invalidated**
 *  ⇒ 它恒为 0。**但一旦后端落了写入点、值 >0，本行照常显示**（守卫单测钉住这一点），
 *  所以不存在「真值被静默吞掉」的失效模式。
 *  另注：这与 `offline_status='invalidated'`（**可达**，见筛选下拉与表格列）**同名不同物**，别混。 */
const HIDDEN_VERIFY_KEYS = ['invalidated']

function verifyRows(links: Record<string, number>): [string, number][] {
  return Object.entries(links).filter(([k, v]) => !(HIDDEN_VERIFY_KEYS.includes(k) && v === 0))
}

function pickAgent(v: string): void {
  queryForm.value.agent = v
}

async function loadOverview(): Promise<void> {
  overErr.value = ''
  try {
    overview.value = await backflowOverview()
  } catch (e) {
    if (e instanceof ApiError) overErr.value = `总览加载失败（${e.code}）：${e.message}`
    else throw e
  }
}

async function loadIfaces(): Promise<void> {
  ifacesLoading.value = true
  try {
    const r = await metricsInterfaces(null, '7d')
    const seen = new Set<string>()
    for (const row of r.request) if (row.interface) seen.add(row.interface)
    for (const row of r.llm) if (row.interface) seen.add(row.interface)
    ifaces.value = [...seen].sort()
  } catch {
    ifaces.value = [] // 可选筛选：失败留空不影响主体
  } finally {
    ifacesLoading.value = false
  }
}

async function doSearch(p = 1): Promise<void> {
  loading.value = true
  errorMsg.value = ''
  try {
    const q: BackflowQuery = {
      agent: queryForm.value.agent.trim() || undefined,
      interface: queryForm.value.interface.trim() || undefined,
      layer: queryForm.value.layer || undefined,
      status: queryForm.value.status || undefined,
      watch: queryForm.value.watch || undefined,
      page: p,
      page_size: pageSize,
    }
    const res = await backflowClusters(q)
    items.value = res.items
    total.value = res.total
    page.value = p
  } catch (e) {
    if (e instanceof ApiError) {
      errorMsg.value = `查询失败（${e.code}）：${e.message}`
      items.value = []
    } else {
      throw e
    }
  } finally {
    loading.value = false
  }
}

function resetAndSearch(): void {
  void doSearch(1)
}

function toDetail(row: BackflowCluster): void {
  void router.push({ name: 'backflow-cluster', params: { clusterId: row.cluster_id } })
}

// 批 33 删除：原 `toTrace()`（列表页「代表 trace」列 → trace 详情）。
// 删除理由 = 用户两次反馈的成因就在这里：该链接是行内**唯一长得像入口的元素**，
// 而「点整行进簇详情」没有任何视觉提示 ⇒ 用户点它、落到 trace 事件页、找不到认领按钮。
// 该跳转在**详情页**仍有出口（P1-12 的「代表 trace ↗」），此处删掉不造成死胡同。

function refresh(): void {
  void loadAgents(true)
  void loadOverview()
  void loadIfaces()
  void doSearch(page.value)
}

onMounted(() => {
  void loadAgents()
  void loadIfaces()
  void loadOverview()
  void doSearch(1)
})

function agentCounts(): BackflowByAgent[] {
  return overview.value?.by_agent ?? []
}
</script>

<template>
  <div>
    <!-- 页头一句话（批 29）：此前进页第一眼就是四张卡 + 一表，全是内部黑话，
         新用户既不知道「错误闭环」是条什么流程、也不知道该从哪看起。
         刻意只一句 —— 本页只有 23 条数据，撑不起一段教程，写长了反而没人读。 -->
    <p class="intro">{{ BACKFLOW_INTRO }}</p>

    <!-- 总览卡：cluster 状态分布 / verify 分布 / to_fix（近似值标注）/ by_agent 小分布 -->
    <section v-if="overview" class="cards">
      <div class="card">
        <strong>错误簇状态</strong>
        <span class="sub">{{ TERM.cluster }}</span>
        <ul class="kv">
          <li v-for="(v, k) in overview.clusters" :key="k">
            <span class="dot" :class="`st-${k}`" />
            <span>{{ statusLabel(k) }}</span><b>{{ v }}</b>
          </li>
        </ul>
      </div>
      <div class="card">
        <!-- ⚠️ 本卡的键是 **verify_status（回归验证）**，不是 offline_status ——
             后端 backflow.py:457-462 明确 `group_by(ErrorCaseLink.verify_status)`，
             值域 = pending/passed/failed/invalidated/superseded。
             我第一版按 offline 去映射，真机上只有 `invalidated` 撞上、其余全兜底成裸键，
             当场抓回（[[measurement-scope-is-not-claim-scope]] 同族：映射对象搞错层）。 -->
        <strong>回归验证结果</strong>
        <span class="sub">{{ TERM.link }}回跑的结果分布</span>
        <ul class="kv">
          <li v-for="[k, v] in verifyRows(overview.links)" :key="k">
            <!-- 改前此处渲染 `{{ k }}` = 后端裸键（pending / passed …），
                 同一组值在别处是中文，新手对不上号。
                 verifyRows：值为 0 的不可达态（invalidated）不占位，见函数注释。 -->
            <span>{{ verifyShort(k) }}</span><b>{{ v }}</b>
          </li>
        </ul>
      </div>
      <div class="card">
        <strong>待修复集</strong>
        <!-- 口径（批 29 改准）：真实谓词 = offline_status='active' **且**
             verify_status ∈ (pending, failed)（backend/app/api/backflow.py:466-471）。
             原先此处的备注「近似值：本平台无 offline 权威集，以…代理」已删 ——
             与其讲一串「近似谁」的内部黑话，不如把**它到底数什么**说清。 -->
        <span class="sub">已推给 offline 侧、但还没通过回归验证的用例数</span>
        <p class="tofix">{{ overview.to_fix }} 条</p>
      </div>
      <div class="card grow">
        <strong>待处置（按 agent）</strong>
        <span class="sub">还没人认领 / 正在复核的簇，按智能体分组</span>
        <ul v-if="agentCounts().length" class="kv">
          <li v-for="a in agentCounts()" :key="a.agent">
            <span>{{ agentDisplay(a.agent) }}</span>
            <b>{{ a.open }} 未处置 · {{ a.claim }} 复核中</b>
          </li>
        </ul>
        <p v-else class="muted note">暂无 open/claim cluster</p>
      </div>
    </section>
    <p v-if="overErr" class="error-text">{{ overErr }}</p>

    <form class="panel query" @submit.prevent="resetAndSearch">
      <label class="agent-field">
        <select :value="queryForm.agent" class="sel" @change="pickAgent(($event.target as HTMLSelectElement).value)">
          <option value="">全站 agent</option>
          <option v-for="a in agents" :key="a" :value="a">{{ agentDisplay(a) }}</option>
        </select>
        <span v-if="agentsLoading" class="muted hint">载入中…</span>
      </label>
      <label class="agent-field">
        <select :value="queryForm.interface" class="sel" @change="queryForm.interface = ($event.target as HTMLSelectElement).value">
          <option value="">全部接口</option>
          <option v-if="ifacesLoading" disabled>载入中…</option>
          <option v-for="i in ifaces" :key="i" :value="i">{{ i }}</option>
        </select>
      </label>
      <label class="agent-field">
        <select :value="queryForm.layer" class="sel" @change="queryForm.layer = ($event.target as HTMLSelectElement).value">
          <option v-for="o in LAYER_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</option>
        </select>
      </label>
      <label class="agent-field">
        <select :value="queryForm.status" class="sel" @change="queryForm.status = ($event.target as HTMLSelectElement).value">
          <option v-for="o in STATUS_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</option>
        </select>
      </label>
      <label class="agent-field">
        <select :value="queryForm.watch" class="sel" @change="queryForm.watch = ($event.target as HTMLSelectElement).value">
          <option v-for="o in WATCH_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</option>
        </select>
      </label>
      <button class="btn" type="submit" :disabled="loading">{{ loading ? '查询中…' : '查询' }}</button>
      <button class="btn-ghost" type="button" @click="refresh">刷新</button>
    </form>

    <p v-if="errorMsg" class="error-text">{{ errorMsg }}</p>

    <div class="panel list">
      <p v-if="!loading && items.length === 0" class="muted">无命中 cluster（可放宽筛选重试）</p>
      <table v-else>
        <thead>
          <tr>
            <th>状态</th>
            <!-- 批 35-B（需求①）：删「现在轮谁」列。批 33 已加【操作】列作显式入口，
                 两列说的是同一件事；且 35-B 撤除写面后「要不要你动手」在 online 侧
                 已无事可做，留着会把用户引向一个不存在的动作（假承诺）。 -->
            <th>agent / 接口</th>
            <th>错误</th>
            <th>次数<span class="th-sub">同类失败出现几次</span></th>
            <th>修复版本<span class="th-sub">{{ TERM.fixVersion }}</span></th>
            <!-- 补列（批 29）：本列是筛选下拉「offline 态」的承载物 ——
                 改前能选不能见，选完了页面上无处对照（与 L1/L2 同病）。 -->
            <th>offline 态<span class="th-sub">{{ TERM.offlineStatus }}</span></th>
            <!-- 批 33：本列是用户两次反馈后加的**显式入口**。成因见 toDetail 上方注释。 -->
            <th>操作<span class="th-sub">点它进这一簇的详情</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in items" :key="row.cluster_id" @click="toDetail(row)">
            <td>
              <span class="status" :class="statusCls(row.status)">{{ statusLabel(row.status) }}</span>
              <span class="muted small" v-if="row.generation > 1">gen{{ row.generation }}</span>
            </td>
            <td>
              <div>{{ agentDisplay(row.agent) }}</div>
              <div class="muted small">{{ row.interface }}</div>
            </td>
            <td class="err">
              <div>{{ row.error_type }}</div>
              <div class="muted small" :title="row.error_msg ?? ''">{{ row.error_msg }}</div>
            </td>
            <td>{{ row.count }}</td>
            <td>{{ row.fix_version || '-' }}</td>
            <td>
              <span v-if="row.link" class="status" :class="statusCls(row.link.offline_status)">
                {{ offlineShort(row.link.offline_status) }}
              </span>
              <span v-else class="muted">-</span>
            </td>
            <td>
              <!-- 按 @click.stop 而非只依赖行点击：本按钮是**显式入口**，
                   用户点的就是这个按钮本身，不该再靠事件冒泡兜底（冒泡一旦被上层
                   重构掉，这里会静默变成死按钮）。行为与行点击完全一致。 -->
              <button
                class="go" :class="{ need: taskState(row).mine }"
                type="button" @click.stop="toDetail(row)"
              >{{ taskState(row).mine ? '去处理 →' : '查看 →' }}</button>
            </td>
          </tr>
        </tbody>
      </table>

      <div class="foot">
        <!-- 批 29 删掉原「· 现行 link：{{ linkOffline(items[0].link.offline_status) }}」：
             它取的是 **items[0]（表格第一行）自己的 link**，措辞却像全页/全站的值
             （`api/types.ts:237` 写明「list 侧**每个 cluster 一个**」）⇒ 纯误导。
             补了「offline 态」列之后，每行的值已在行内可见，这句没有剩余信息量。 -->
        <span class="muted">共 {{ total }} 个错误簇</span>
        <span v-if="total > pageSize">
          <button class="btn-ghost" type="button" :disabled="page <= 1" @click="doSearch(page - 1)">上一页</button>
          <span class="page-no">{{ page }} / {{ maxPages }}</span>
          <button
            class="btn-ghost" type="button"
            :disabled="page >= maxPages || items.length < pageSize"
            @click="doSearch(page + 1)"
          >下一页</button>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 页头一句话（批 29）：新手进页第一眼要能知道「这是什么、从哪看起」 */
.intro {
  margin: 0 0 12px;
  padding: 10px 12px;
  border-left: 3px solid var(--brand);
  background: var(--panel);
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.6;
  color: #374151;
}

/* 卡片标题下的小字释义（就地、不折叠） */
.sub {
  display: block;
  margin: -4px 0 8px;
  font-size: 12px;
  color: var(--muted);
}

/* 表头第二行小字：把原本只藏在 title（hover 才见）里的解释提到明面 */
.th-sub {
  display: block;
  font-weight: 400;
  font-size: 11px;
  color: var(--muted);
  white-space: normal;
}

.cards {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.card {
  flex: 1;
  min-width: 220px;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-panel);
  padding: 10px 12px;
}

.card strong {
  font-size: 13px;
  color: var(--muted);
  display: block;
  margin-bottom: 8px;
}

.card.grow {
  flex: 2;
}

.kv {
  list-style: none;
  margin: 0;
  padding: 0;
}

.kv li {
  display: flex;
  /* P2-27：原为 space-between —— 但「cluster 状态」那张卡的 li 有**三个**子元素
     （色点 / 标签 / 数字），space-between 会把**中间的标签**甩到剩余空间正中，
     色点与标签之间因此空出大片。改 flex-start + 数字 margin-left:auto：
     「色点 + 标签」自然相邻（gap 8px），数字仍贴最右。
     同页「link 回查分布」的 li 只有两个子元素，此改法对它**逐像素等价**（本就是 span 左 / b 右）。 */
  justify-content: flex-start;
  align-items: center;
  gap: 8px;
  padding: 2px 0;
  font-size: 13px;
}

.kv b {
  font-weight: 600;
  margin-left: auto;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  display: inline-block;
}

/* 批 29：原为 22px —— 同排另外三张卡的数值是 13px（`.kv b`），两套字号并排不成套
   （同 P1-20「同级 KPI 卡不同形」一族）。统一到 13px，靠 font-weight 保持一点点主次。 */
.tofix {
  font-size: 13px;
  font-weight: 600;
  margin: 4px 0;
}

.note {
  font-size: 12px;
}

.query {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.agent-field {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.sel {
  padding: 5px 8px;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 13px;
  background: #fff;
}

.hint {
  font-size: 12px;
}

/* 批 33：行内**显式入口**。此前整行的可点击性只由 `cursor: pointer` 表达，
   肉眼不可见 ⇒ 用户找不到进簇详情的门（两次反馈）。本按钮是那扇门的可见形态。
   ⚠️ 批 35-B：上游的「现在轮谁」列已删，`.need`（红字）现在**只**靠 `.go` 自己表达
   「这一簇还等着人修」；原注释里「与列同色连成一条视线」的说法随之作废。 */
.go {
  border: 1px solid var(--border);
  background: none;
  border-radius: 4px;
  padding: 3px 8px;
  font-size: 12px;
  color: var(--brand);
  cursor: pointer;
  white-space: nowrap;
}

.go.need {
  color: var(--error);
  border-color: var(--hl-red);
  font-weight: 600;
}

.go:hover { background: var(--bg); }

table {
  width: 100%;
  border-collapse: collapse;
  /* 批 31：原来 `table-layout` 默认 auto —— 窄列（状态 / 次数 / 轮谁）被内容撑开，
     宽列（错误 / 时间）反被挤到难看。固定布局 + 逐列定宽后各列不再互相抢；
     「错误」列刻意**不给宽度**，由它吃掉剩余空间（内容最长、最需要宽）。 */
  table-layout: fixed;
}

/* ⚠️ 改列 = 改这张表。批 33（删 3 列 + 加「操作」）与批 35-B（删「现在轮谁」）都动过它，
   每次都**必须同步改编号**；漏改的症状是列宽错位（宽度还在，只是套到了别的列上），
   **不报错、不红测**，只能靠眼睛看出来。 */
th:nth-child(1) { width: 80px; }    /* 状态 */
th:nth-child(2) { width: 16%; }     /* agent / 接口 */
th:nth-child(4) { width: 56px; }    /* 次数 */
th:nth-child(5) { width: 96px; }    /* 修复版本 */
th:nth-child(6) { width: 116px; }   /* offline 态 */
th:nth-child(7) { width: 96px; }    /* 操作 */

th, td {
  text-align: left;
  padding: 6px 8px;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
}

th {
  color: var(--muted);
  font-weight: 500;
  white-space: nowrap;
}

tbody tr {
  cursor: pointer;
}

tbody tr:hover {
  background: var(--hover-row);
}

.err {
  max-width: 240px;
  word-break: break-all;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}

.short {
  max-width: 130px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.small {
  font-size: 12px;
}

.status {
  font-size: 12px;
  padding: 1px 6px;
  border-radius: 3px;
  white-space: nowrap;
}

.st-open, .st-assembled { background: #e8eaf0; color: #4b5563; }
.st-claim, .st-draft { background: #fdf1dc; color: #9a6b00; }
.st-fixed, .st-active { background: #e7f3e9; color: var(--ok); }
.st-inactive { background: #e8eaf0; color: #6b7280; }
.st-needs_review, .st-invalidated { background: var(--hl-red); color: var(--error); }

/* 批 35-B：`.wheel` / `.wheel.need` 随「现在轮谁」列一并删除 —— 模板已无使用者。 */

.foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
}

.page-no {
  margin: 0 8px;
  color: var(--muted);
}
</style>
