import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Empty,
  Input,
  Segmented,
  Select,
  Space,
  Spin,
  Switch,
  Tag,
  Typography,
} from "antd";

import type { ChatEndpoint } from "@llm-gateway/contracts";

import { useGatewaySession } from "../../app/session";
import { useModels } from "../models/useModels";
import { useChatStream, type ChatUiMessage } from "./useChatStream";

const { TextArea } = Input;
const { Text, Title } = Typography;

export function ChatPage() {
  const { apiKey } = useGatewaySession();
  const { models, loading: modelsLoading, error: modelsError } = useModels(apiKey);
  const [route, setRoute] = useState("default");
  const [endpoint, setEndpoint] = useState<ChatEndpoint>("chat.completions");
  const [stream, setStream] = useState(true);
  const [input, setInput] = useState("");
  const {
    messages,
    streaming,
    error,
    send,
    stop,
    clear,
    setError,
  } = useChatStream();

  useEffect(() => {
    if (!models.some((model) => model.id === route) && models.length) {
      const preferred = models.find((model) => model.id === "default") ?? models[0];
      setRoute(preferred.id);
    }
  }, [models, route]);

  const currentRoute = useMemo(
    () => models.find((model) => model.id === route),
    [models, route],
  );

  const submit = async () => {
    if (!apiKey || !input.trim() || streaming) return;
    const value = input;
    setInput("");
    await send({ apiKey, endpoint, model: route, stream, input: value });
  };

  return (
    <section className="page chat-page">
      <header className="page-heading">
        <div>
          <span className="eyebrow">LIVE WORKSPACE</span>
          <Title level={1}>对话工作台</Title>
          <Text type="secondary">
            一个请求，沿候选顺序寻找当前可用的模型。
          </Text>
        </div>
        <Button onClick={clear} disabled={!messages.length}>
          清空会话
        </Button>
      </header>

      {!apiKey ? (
        <Alert
          className="inline-alert"
          type="warning"
          showIcon
          message="先连接网关"
          description="点击左侧导航底部的“连接”，输入后端配置中的 GATEWAY_API_KEY。密钥只保存在当前标签页。"
        />
      ) : null}
      {modelsError ? (
        <Alert
          className="inline-alert"
          type="error"
          showIcon
          message="模型路由不可用"
          description={modelsError}
        />
      ) : null}
      {error ? (
        <Alert
          className="inline-alert"
          type="error"
          showIcon
          closable
          message={error}
          onClose={() => setError(null)}
        />
      ) : null}

      <div className="chat-workspace">
        <aside className="control-rail">
          <div className="rail-section">
            <span className="field-label">接口协议</span>
            <Segmented
              block
              value={endpoint}
              onChange={(value) => setEndpoint(value as ChatEndpoint)}
              options={[
                { label: "Chat", value: "chat.completions" },
                { label: "Responses", value: "responses" },
              ]}
            />
          </div>

          <div className="rail-section">
            <span className="field-label">模型路由</span>
            <Select
              className="full-width"
              value={route}
              loading={modelsLoading}
              onChange={setRoute}
              options={models.map((model) => ({
                value: model.id,
                label: model.id,
              }))}
              placeholder="选择路由"
            />
            {currentRoute ? (
              <div className="candidate-stack">
                {currentRoute.candidates.map((candidate, index) => (
                  <div className="candidate-line" key={candidate.id}>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <div>
                      <strong>{candidate.provider}</strong>
                      <small>{candidate.model}</small>
                    </div>
                    <i className={candidate.available ? "dot online" : "dot"} />
                  </div>
                ))}
              </div>
            ) : (
              <div className="rail-placeholder">暂无候选模型</div>
            )}
          </div>

          <div className="rail-section horizontal">
            <div>
              <span className="field-label">流式输出</span>
              <small>SSE 实时增量</small>
            </div>
            <Switch checked={stream} onChange={setStream} />
          </div>
        </aside>

        <div className="conversation-panel">
          <div className="conversation-meta">
            <Space size={8}>
              <Tag bordered={false}>{endpoint === "responses" ? "Responses" : "Chat"}</Tag>
              <Tag bordered={false}>{stream ? "STREAM" : "JSON"}</Tag>
            </Space>
            <Text type="secondary">{messages.length} 条消息</Text>
          </div>

          <div className="message-viewport" aria-live="polite">
            {messages.length === 0 ? (
              <div className="empty-conversation">
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description={
                    <span>从一个具体问题开始。网关会记录尝试路径与 token 用量。</span>
                  }
                />
              </div>
            ) : (
              messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))
            )}
          </div>

          <div className="composer">
            <TextArea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void submit();
                }
              }}
              autoSize={{ minRows: 3, maxRows: 8 }}
              placeholder="输入问题，Enter 发送，Shift + Enter 换行"
              disabled={!apiKey}
            />
            <div className="composer-actions">
              <Text type="secondary">结果由上游模型生成，请核验关键事实。</Text>
              {streaming ? (
                <Button danger onClick={stop}>
                  停止生成
                </Button>
              ) : (
                <Button
                  type="primary"
                  loading={modelsLoading}
                  disabled={!apiKey || !input.trim()}
                  onClick={() => void submit()}
                >
                  发送请求
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function MessageBubble({ message }: { message: ChatUiMessage }) {
  const isUser = message.role === "user";
  return (
    <article className={`message ${isUser ? "user" : "assistant"}`}>
      <div className="message-mark">{isUser ? "你" : "AI"}</div>
      <div className="message-body">
        <div className="message-label">
          <span>{isUser ? "YOU" : "GATEWAY"}</span>
          {message.model ? <small>{message.model}</small> : null}
        </div>
        <div className="message-content">
          {message.content || (message.status === "streaming" ? <Spin size="small" /> : "")}
        </div>
        {message.status === "cancelled" ? <small>已停止</small> : null}
        {message.status === "error" ? <small>生成失败</small> : null}
        {message.totalTokens ? <small>{message.totalTokens} tokens</small> : null}
      </div>
    </article>
  );
}
