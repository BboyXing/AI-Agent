import { useState } from "react";
import { Tag, Typography } from "antd";

const { Text, Title } = Typography;

type Stage = {
  id: string;
  index: string;
  kicker: string;
  title: string;
  flowTitle: string;
  summary: string;
  detail: string;
  input: string;
  output: string;
  implementation: Array<{ label: string; path: string }>;
  invariants: string[];
};

const stages: Stage[] = [
  {
    id: "client",
    index: "01",
    kicker: "WEB CLIENT",
    title: "请求编排与入口",
    flowTitle: "客户端",
    summary: "组装协议、模型路由和消息历史。",
    detail:
      "浏览器只在当前标签页保存 GATEWAY_API_KEY。用户选择 Chat Completions 或 Responses 协议、逻辑模型路由、流式开关并发送消息。客户端统一把两种服务端协议转换成 UI 流事件，因此聊天界面只维护一套消息状态。",
    input: "用户消息、model route、endpoint、stream=true/false",
    output: "带 Bearer Key 的 POST /v1/chat/completions 或 POST /v1/responses",
    implementation: [
      { label: "会话密钥与连接状态", path: "apps/web/src/app/session.tsx" },
      { label: "协议与路由选择", path: "apps/web/src/features/chat/ChatPage.tsx" },
      { label: "请求及 SSE 统一解析", path: "apps/web/src/features/chat/api/stream.ts" },
      { label: "会话状态更新", path: "apps/web/src/features/chat/useChatStream.ts" },
    ],
    invariants: [
      "DEEPSEEK_API_KEY 永不进入浏览器",
      "sessionStorage 只保存网关访问 Key",
      "两种接口最终都归一为 start / delta / done / error",
    ],
  },
  {
    id: "edge",
    index: "02",
    kicker: "API EDGE",
    title: "绑定、鉴权与限流",
    flowTitle: "API 边界",
    summary: "Request ID、DTO 校验、Identity 与 429 控制。",
    detail:
      "FastAPI 为每个请求生成或复用 X-Request-ID。路由先绑定 Pydantic DTO，再执行统一的 Identity 依赖：解析 Bearer Key、做恒定时间摘要比较，并按 Key 做进程内固定窗口限流。任何受保护路由都复用同一实现，不需要重复编写鉴权代码。",
    input: "HTTP JSON、Authorization: Bearer、可选 X-Request-ID",
    output: "通过校验的 DTO、IdentityContext，或 401 / 422 / 429",
    implementation: [
      { label: "应用、中间件与异常格式", path: "apps/api/src/llm_gateway/main.py" },
      { label: "统一 Identity 依赖", path: "apps/api/src/llm_gateway/api/deps.py" },
      { label: "Key 摘要鉴权", path: "apps/api/src/llm_gateway/services/identity.py" },
      { label: "固定窗口限流", path: "apps/api/src/llm_gateway/services/rate_limit.py" },
      { label: "两组公开 DTO", path: "apps/api/src/llm_gateway/schemas/" },
    ],
    invariants: [
      "缺少或错误 Key 返回 401 与 WWW-Authenticate",
      "超过额度返回 429 并携带 Retry-After",
      "结构化流式请求在进入网关前返回 422",
    ],
  },
  {
    id: "runtime",
    index: "03",
    kicker: "LIFESPAN",
    title: "运行期装配",
    flowTitle: "运行时",
    summary: "加载配置，初始化服务并挂载 app.state。",
    detail:
      "启动时读取 GATEWAY_CONFIG_FILE；变量为空时回退 gateway.example.yaml。YAML 完成环境变量替换和引用校验后，lifespan 创建 PromptRegistry、SQLite、HTTPX、Adapter、ModelRouter、Gateway、Identity 与 UsageService，并统一挂载到 app.state。关闭时释放数据库和 HTTP 连接。",
    input: "YAML、进程环境变量、Prompt 模板、SQLite 路径",
    output: "app.state.gateway 及完整服务容器",
    implementation: [
      { label: "配置加载和引用校验", path: "apps/api/src/llm_gateway/core/config.py" },
      { label: "运行期构建与卸载", path: "apps/api/src/llm_gateway/core/runtime.py" },
      { label: "FastAPI lifespan", path: "apps/api/src/llm_gateway/main.py" },
      { label: "SQLite 初始化", path: "apps/api/src/llm_gateway/persistence/db.py" },
    ],
    invariants: [
      "显式指定的配置文件不存在时启动失败",
      "供应商 Key 为空时服务仍启动，候选标记为 unavailable",
      "Prompt、Model、Provider、Route 引用在启动阶段校验",
    ],
  },
  {
    id: "routing",
    index: "04",
    kicker: "GATEWAY CORE",
    title: "路由、Prompt 与候选队列",
    flowTitle: "路由核心",
    summary: "逻辑模型解析为有序供应商候选。",
    detail:
      "请求中的 model 是逻辑路由名而不是供应商模型名。ModelRouter 解析出有序候选，例如 default 首先使用 deepseek-chat，再降级到 OpenAI、Anthropic。渲染 route 对应的 Prompt 后插入 system message；若请求携带 JSON Schema，则追加只返回 JSON 的强约束指令。",
    input: "model route、消息、可选 JSON Schema",
    output: "ResolvedRoute、完整 CanonicalMessage，以及 pending 请求记录",
    implementation: [
      { label: "逻辑路由与候选解析", path: "apps/api/src/llm_gateway/gateway/router.py" },
      { label: "Prompt 严格渲染", path: "apps/api/src/llm_gateway/services/prompts.py" },
      { label: "Prompt / Schema 注入", path: "apps/api/src/llm_gateway/gateway/service.py" },
      { label: "默认路由配置", path: "apps/api/config/gateway.example.yaml" },
    ],
    invariants: [
      "default 的第一候选是 deepseek-chat",
      "模型配置引用不存在的供应商时启动失败",
      "请求只接受文本消息，不接受工具和多模态内容",
    ],
  },
  {
    id: "adapter",
    index: "05",
    kicker: "PROVIDER LAYER",
    title: "供应商适配与降级",
    flowTitle: "供应商",
    summary: "OpenAI 兼容协议与 Anthropic 原生协议。",
    detail:
      "Gateway 按候选顺序调用 Adapter。DeepSeek 与 OpenAI 共用 OpenAI Chat Completions Adapter；Anthropic 使用 Messages Adapter。每次尝试单独记录 ordinal、provider、model、延迟、HTTP 状态和 usage。连接错误、超时、429、5xx 与结构校验失败可进入下一候选；普通 4xx 立即终止。",
    input: "Candidate、CanonicalMessage、timeout 与 Schema",
    output: "GatewayResult 或标准化 GatewayEvent 序列",
    implementation: [
      { label: "OpenAI / DeepSeek Adapter", path: "apps/api/src/llm_gateway/gateway/adapters/openai.py" },
      { label: "Anthropic Adapter", path: "apps/api/src/llm_gateway/gateway/adapters/anthropic.py" },
      { label: "候选循环与流式边界", path: "apps/api/src/llm_gateway/gateway/service.py" },
      { label: "JSON Schema 校验", path: "apps/api/src/llm_gateway/gateway/structured.py" },
    ],
    invariants: [
      "流式响应在首个可见 chunk 前允许切换候选",
      "首段内容发送后不再切换供应商，避免拼接半截回答",
      "缺少供应商 Key 时跳过该候选并写 trace",
    ],
  },
  {
    id: "projector",
    index: "06",
    kicker: "PUBLIC CONTRACT",
    title: "协议投影",
    flowTitle: "响应投影",
    summary: "内部事件映射为 Chat Chunk 或 Responses Event。",
    detail:
      "Gateway 内部不直接依赖某个公开协议。Projector 将统一事件转换为 Chat Completion chunk 与 [DONE]，或转换为 Responses API 的 response.created、output_text.delta、response.completed 事件。非流式调用则输出对应的 chat.completion 或 response 对象。",
    input: "GatewayResult 或 GatewayEvent 序列",
    output: "application/json，或 text/event-stream",
    implementation: [
      { label: "SSE 与 JSON 投影", path: "apps/api/src/llm_gateway/gateway/projector.py" },
      { label: "Chat Completion 路由", path: "apps/api/src/llm_gateway/api/routes/chat_completions.py" },
      { label: "Responses 路由", path: "apps/api/src/llm_gateway/api/routes/responses.py" },
      { label: "浏览器端反向归一", path: "apps/web/src/shared/sse/parser.ts" },
    ],
    invariants: [
      "流开始前失败仍返回可映射的 HTTP 错误",
      "流开始后失败使用对应协议的 SSE error 事件",
      "公开响应中的 model 使用实际上游模型名",
    ],
  },
  {
    id: "observability",
    index: "07",
    kicker: "USAGE & TRACE",
    title: "计量、追踪与查询",
    flowTitle: "可观测性",
    summary: "请求、尝试、trace 和 token 统一落库。",
    detail:
      "UsageService 在请求开始时创建 pending 记录，每次候选尝试创建 attempt，并写入结构化 trace。成功、失败、取消或断开时更新最终状态。token 只使用供应商返回值，不做本地估算；trace 不保存 API Key、完整 Prompt 或完整回答。前端用量页读取聚合和明细。",
    input: "request_id、候选结果、供应商 usage、错误和延迟",
    output: "llm_requests、llm_attempts、trace_events 与查询 API",
    implementation: [
      { label: "请求 / 尝试 / trace 写入", path: "apps/api/src/llm_gateway/services/usage.py" },
      { label: "SQLite Repository", path: "apps/api/src/llm_gateway/persistence/repository.py" },
      { label: "用量查询端点", path: "apps/api/src/llm_gateway/api/routes/usage.py" },
      { label: "前端用量控制台", path: "apps/web/src/features/usage/UsagePage.tsx" },
    ],
    invariants: [
      "未知 token 保持 NULL，不填充猜测值",
      "客户端取消请求记录 cancelled 和 client_cancelled",
      "每个公开请求都可通过 X-Request-ID 回溯",
    ],
  },
];

const startupSteps = [
  { code: "ENV", title: "读取 YAML", text: "替换 ${VAR}，校验引用" },
  { code: "BOOT", title: "构建服务", text: "Prompt、HTTP、DB、Adapter" },
  { code: "STATE", title: "挂载运行时", text: "app.state.gateway + services" },
  { code: "READY", title: "健康就绪", text: "/readyz 检查 SQLite" },
];

const supportSystems = [
  {
    code: "CFG",
    title: "Config Loader",
    text: "YAML 是供应商、模型、候选顺序和限额的唯一来源。",
  },
  {
    code: "IDN",
    title: "Identity",
    text: "统一 Bearer 校验和按 Key 固定窗口限流。",
  },
  {
    code: "HTTP",
    title: "HTTPX Client",
    text: "生命周期内复用一个异步连接池。",
  },
  {
    code: "DB",
    title: "SQLite WAL",
    text: "请求、候选尝试和关键 trace 的持久记录。",
  },
];

const failureRules = [
  {
    code: "401",
    title: "网关鉴权失败",
    behavior: "缺少或错误 Bearer Key，返回 WWW-Authenticate，不调用供应商。",
  },
  {
    code: "429",
    title: "客户端限流",
    behavior: "按 API Key 计数，返回 Retry-After，不创建上游请求。",
  },
  {
    code: "5xx",
    title: "可重试上游错误",
    behavior: "连接错误、超时、429 和 5xx 进入下一候选，并记录失败 attempt。",
  },
  {
    code: "4xx",
    title: "不可重试上游错误",
    behavior: "普通 400、401、404 立即终止，避免对其他供应商发送同样错误请求。",
  },
  {
    code: "SCHEMA",
    title: "结构校验失败",
    behavior: "非流式回答不是合法 JSON 或不符合 Schema 时切换下一候选。",
  },
  {
    code: "BREAK",
    title: "流中断",
    behavior: "首个 chunk 前可降级；已输出内容后停止切换并发送 SSE error。",
  },
];

export function ArchitecturePage() {
  const [selectedId, setSelectedId] = useState(stages[0].id);
  const selected = stages.find((stage) => stage.id === selectedId) ?? stages[0];

  const selectStage = (stageId: string) => {
    setSelectedId(stageId);
  };

  return (
    <section className="page architecture-page">
      <header className="page-heading architecture-heading">
        <div>
          <span className="eyebrow">SYSTEM BLUEPRINT / 00</span>
          <Title level={1}>架构全流程</Title>
          <Text type="secondary">
            从浏览器请求到供应商响应，再到 SQLite 计量记录的完整执行路径。
          </Text>
        </div>
        <div className="architecture-version">
          <span>MONOREPO</span>
          <strong>WEB + API</strong>
          <small>DeepSeek first · text only</small>
        </div>
      </header>

      <section className="startup-strip" aria-labelledby="startup-title">
        <div className="startup-label">
          <span>BOOT SEQUENCE</span>
          <strong id="startup-title">启动装配</strong>
        </div>
        <div className="startup-steps">
          {startupSteps.map((step, index) => (
            <div className="startup-step" key={step.code}>
              <span className="startup-code">{step.code}</span>
              <div>
                <strong>{step.title}</strong>
                <small>{step.text}</small>
              </div>
              {index < startupSteps.length - 1 ? <i aria-hidden="true">→</i> : null}
            </div>
          ))}
        </div>
      </section>

      <div className="architecture-board">
        <header className="architecture-board-heading">
          <div>
            <span className="board-kicker">REQUEST EXECUTION MAP</span>
            <strong>一次模型调用的七个关键断面</strong>
            <span className="mobile-flow-hint">横向滑动查看完整流程 →</span>
          </div>
          <Tag bordered={false}>CLICK A NODE TO INSPECT</Tag>
        </header>

        <div className="flow-lane" role="list" aria-label="请求执行流程">
          {stages.map((stage, index) => (
            <div className="flow-slot" role="listitem" key={stage.id}>
              <button
                type="button"
                className={`flow-node ${selected.id === stage.id ? "active" : ""}`}
                onClick={() => selectStage(stage.id)}
                aria-pressed={selected.id === stage.id}
                aria-label={`${stage.index} ${stage.title}：${stage.summary}`}
              >
                <span className="flow-node-index">{stage.index}</span>
                <small>{stage.kicker}</small>
                <strong>{stage.flowTitle}</strong>
                <p>{stage.summary}</p>
              </button>
              {index < stages.length - 1 ? (
                <span className="flow-connector" aria-hidden="true">
                  <i />
                </span>
              ) : null}
            </div>
          ))}
        </div>

        <div className="response-lane">
          <span>RETURN PATH</span>
          <i aria-hidden="true" />
          <strong>JSON object</strong>
          <em>/</em>
          <strong>SSE events</strong>
          <i aria-hidden="true" />
          <span>BROWSER STATE</span>
        </div>

        <div className="support-systems">
          <div className="support-label">
            <span>RUNTIME SUPPORT</span>
            <small>跨请求复用的基础设施</small>
          </div>
          <div className="support-grid">
            {supportSystems.map((system) => (
              <div className="support-card" key={system.code}>
                <span>{system.code}</span>
                <strong>{system.title}</strong>
                <p>{system.text}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <section className="architecture-inspector" aria-live="polite">
        <div className="inspector-main">
          <span className="inspector-number">{selected.index}</span>
          <div className="inspector-copy">
            <span className="eyebrow">{selected.kicker}</span>
            <Title level={2}>{selected.title}</Title>
            <p>{selected.detail}</p>
            <div className="implementation-list">
              {selected.implementation.map((item) => (
                <div className="implementation-line" key={item.path}>
                  <span>{item.label}</span>
                  <code>{item.path}</code>
                </div>
              ))}
            </div>
          </div>
        </div>
        <aside className="inspector-side">
          <div>
            <span className="field-label">INPUT</span>
            <p>{selected.input}</p>
          </div>
          <div>
            <span className="field-label">OUTPUT</span>
            <p>{selected.output}</p>
          </div>
          <div className="invariant-block">
            <span className="field-label">IMPLEMENTATION RULES</span>
            {selected.invariants.map((item) => (
              <p key={item}>
                <i />
                {item}
              </p>
            ))}
          </div>
        </aside>
      </section>

      <section className="implementation-ledger" aria-labelledby="ledger-title">
        <header>
          <div>
            <span className="eyebrow">IMPLEMENTATION LEDGER</span>
            <Title level={2} id="ledger-title">
              逐阶段实现说明
            </Title>
          </div>
          <Text type="secondary">
            点击任一行，回到上方查看该阶段的输入、输出与约束。
          </Text>
        </header>
        <div className="ledger-rows">
          {stages.map((stage) => (
            <button
              type="button"
              className={`ledger-row ${selected.id === stage.id ? "active" : ""}`}
              key={stage.id}
              onClick={() => selectStage(stage.id)}
            >
              <span className="ledger-index">{stage.index}</span>
              <span className="ledger-title">
                <strong>{stage.title}</strong>
                <small>{stage.summary}</small>
              </span>
              <span className="ledger-paths">
                {stage.implementation.slice(0, 2).map((item) => (
                  <code key={item.path}>{item.path}</code>
                ))}
              </span>
              <span className="ledger-arrow" aria-hidden="true">
                ↗
              </span>
            </button>
          ))}
        </div>
      </section>

      <div className="architecture-lower-grid">
        <section className="failure-panel" aria-labelledby="failure-title">
          <header>
            <span className="eyebrow">FAILURE SEMANTICS</span>
            <Title level={2} id="failure-title">
              失败与降级
            </Title>
          </header>
          <div className="failure-list">
            {failureRules.map((rule) => (
              <div className="failure-row" key={rule.code}>
                <span>{rule.code}</span>
                <div>
                  <strong>{rule.title}</strong>
                  <p>{rule.behavior}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="data-panel" aria-labelledby="data-title">
          <header>
            <span className="eyebrow">PERSISTENCE</span>
            <Title level={2} id="data-title">
              数据与回放
            </Title>
          </header>
          <div className="data-table">
            <div>
              <code>llm_requests</code>
              <span>一次公开请求的最终状态、模型、token 和延迟</span>
            </div>
            <div>
              <code>llm_attempts</code>
              <span>每个候选的尝试顺序、错误、耗时与 usage</span>
            </div>
            <div>
              <code>trace_events</code>
              <span>started、skipped、failed、success、cancelled 等关键事件</span>
            </div>
          </div>
          <div className="privacy-note">
            <strong>审计边界</strong>
            <p>
              数据库和结构化日志不保存 API Key、完整 Prompt 或完整模型回答；请求通过
              request_id 串联。
            </p>
          </div>
        </section>
      </div>
    </section>
  );
}
