import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Drawer,
  Segmented,
  Skeleton,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";

import { useGatewaySession } from "../../app/session";
import {
  fetchCallDetail,
  fetchCalls,
  fetchUsageSummary,
} from "../../shared/api/client";
import type {
  CallDetail,
  CallPage,
  CallRecord,
  UsageSummary,
} from "../../shared/api/types";

const { Title, Text } = Typography;
const PAGE_SIZE = 20;

export function UsagePage() {
  const { apiKey } = useGatewaySession();
  const [days, setDays] = useState(7);
  const [offset, setOffset] = useState(0);
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [calls, setCalls] = useState<CallPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CallDetail | null>(null);

  const range = useMemo(() => {
    const to = new Date();
    const from = new Date(to.getTime() - days * 24 * 60 * 60 * 1000);
    return { from: from.toISOString(), to: to.toISOString() };
  }, [days]);

  useEffect(() => {
    if (!apiKey) return;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    Promise.all([
      fetchUsageSummary(apiKey, range, controller.signal),
      fetchCalls(
        apiKey,
        { ...range, limit: PAGE_SIZE, offset },
        controller.signal,
      ),
    ])
      .then(([nextSummary, nextCalls]) => {
        setSummary(nextSummary);
        setCalls(nextCalls);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "用量查询失败");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [apiKey, range, offset]);

  useEffect(() => {
    if (!apiKey || !selectedId) {
      setDetail(null);
      return;
    }
    const controller = new AbortController();
    fetchCallDetail(apiKey, selectedId, controller.signal)
      .then(setDetail)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "请求明细加载失败");
        }
      });
    return () => controller.abort();
  }, [apiKey, selectedId]);

  const columns: ColumnsType<CallRecord> = [
    {
      title: "请求",
      dataIndex: "request_id",
      key: "request_id",
      width: 210,
      render: (value: string, record) => (
        <button className="link-button" onClick={() => setSelectedId(record.request_id)}>
          {value}
        </button>
      ),
    },
    {
      title: "路由",
      dataIndex: "route",
      key: "route",
      width: 130,
    },
    {
      title: "模型",
      key: "model",
      width: 180,
      render: (_, record) => record.upstream_model ?? "—",
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (value: string) => (
        <Tag color={value === "success" ? "green" : value === "pending" ? "gold" : "red"}>
          {value}
        </Tag>
      ),
    },
    {
      title: "Tokens",
      dataIndex: "total_tokens",
      key: "total_tokens",
      width: 100,
      render: (value: number | null) => value ?? "—",
    },
    {
      title: "耗时",
      dataIndex: "latency_ms",
      key: "latency_ms",
      width: 100,
      render: (value: number | null) => (value == null ? "—" : `${value} ms`),
    },
    {
      title: "时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 190,
      render: (value: string) => formatDate(value),
    },
  ];

  return (
    <section className="page">
      <header className="page-heading">
        <div>
          <span className="eyebrow">OBSERVABILITY</span>
          <Title level={1}>用量记录</Title>
          <Text type="secondary">token 只采用供应商返回值，不做本地估算。</Text>
        </div>
        <Segmented
          value={days}
          onChange={(value) => {
            setDays(Number(value));
            setOffset(0);
          }}
          options={[
            { label: "7 天", value: 7 },
            { label: "30 天", value: 30 },
            { label: "90 天", value: 90 },
          ]}
        />
      </header>

      {!apiKey ? <Alert type="warning" showIcon message="连接网关后可查询用量" /> : null}
      {error ? <Alert type="error" showIcon message={error} /> : null}
      {loading && !summary ? <Skeleton active /> : null}

      <div className="metric-strip">
        <Metric label="请求总数" value={summary?.request_count ?? 0} />
        <Metric label="成功率" value={summary ? summary.success_rate * 100 : 0} suffix="%" precision={1} />
        <Metric label="Token 总量" value={summary?.total_tokens ?? 0} />
        <Metric label="平均延迟" value={summary?.average_latency_ms ?? 0} suffix="ms" precision={0} />
      </div>

      <div className="table-panel">
        <div className="table-heading">
          <div>
            <Title level={3}>请求明细</Title>
            <Text type="secondary">点击 request id 查看候选尝试和 trace。</Text>
          </div>
          <Button onClick={() => setOffset(0)} disabled={offset === 0}>
            回到第一页
          </Button>
        </div>
        <Table
          rowKey="request_id"
          loading={loading}
          columns={columns}
          dataSource={calls?.items ?? []}
          scroll={{ x: 1080 }}
          pagination={{
            current: Math.floor(offset / PAGE_SIZE) + 1,
            pageSize: PAGE_SIZE,
            total: calls?.total ?? 0,
            showSizeChanger: false,
            onChange: (page) => setOffset((page - 1) * PAGE_SIZE),
          }}
        />
      </div>

      <Drawer
        title="调用详情"
        width={620}
        open={Boolean(selectedId)}
        onClose={() => setSelectedId(null)}
      >
        {!detail ? (
          <Skeleton active />
        ) : (
          <div className="detail-stack">
            <DetailLine label="Request ID" value={detail.request_id} />
            <DetailLine label="路由 / Prompt" value={`${detail.route} / ${detail.prompt}`} />
            <DetailLine label="最终模型" value={detail.upstream_model ?? "未选中模型"} />
            <DetailLine
              label="Token"
              value={`${detail.input_tokens ?? "?"} in / ${detail.output_tokens ?? "?"} out`}
            />
            <Title level={4}>候选尝试</Title>
            {detail.attempts.map((attempt) => (
              <div className="attempt-card" key={attempt.id}>
                <div>
                  <strong>{attempt.candidate}</strong>
                  <small>
                    {attempt.provider} / {attempt.upstream_model}
                  </small>
                </div>
                <Tag color={attempt.status === "success" ? "green" : "red"}>
                  {attempt.status}
                </Tag>
                <Text type="secondary">{attempt.latency_ms ?? 0} ms</Text>
                {attempt.error_message ? <code>{attempt.error_message}</code> : null}
              </div>
            ))}
            <Title level={4}>Trace 事件</Title>
            <div className="trace-list">
              {detail.trace.map((event, index) => (
                <div className="trace-line" key={`${event.event_type}-${index}`}>
                  <span>{event.event_type}</span>
                  <small>{formatDate(event.created_at)}</small>
                </div>
              ))}
            </div>
          </div>
        )}
      </Drawer>
    </section>
  );
}

function Metric({
  label,
  value,
  suffix,
  precision = 0,
}: {
  label: string;
  value: number;
  suffix?: string;
  precision?: number;
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <Statistic value={value} suffix={suffix} precision={precision} />
    </div>
  );
}

function DetailLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="detail-line">
      <span>{label}</span>
      <code>{value}</code>
    </div>
  );
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}
