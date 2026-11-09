import { Alert, Empty, Skeleton, Tag, Typography } from "antd";

import { useGatewaySession } from "../../app/session";
import { useModels } from "./useModels";

const { Title, Text } = Typography;

export function ModelsPage() {
  const { apiKey } = useGatewaySession();
  const { models, loading, error } = useModels(apiKey);

  return (
    <section className="page">
      <header className="page-heading">
        <div>
          <span className="eyebrow">ROUTING TABLE</span>
          <Title level={1}>模型路由</Title>
          <Text type="secondary">候选按顺序调用，首个成功响应结束本次路由。</Text>
        </div>
      </header>
      {!apiKey ? (
        <Alert
          type="warning"
          showIcon
          message="连接网关后可读取路由"
        />
      ) : null}
      {error ? <Alert type="error" showIcon message={error} /> : null}
      {loading ? <Skeleton active /> : null}
      {!loading && apiKey && !error && models.length === 0 ? (
        <Empty description="没有已配置的模型路由" />
      ) : null}
      <div className="route-grid">
        {models.map((route) => (
          <article className="route-card" key={route.id}>
            <header>
              <div>
                <span className="eyebrow">ROUTE</span>
                <Title level={2}>{route.id}</Title>
              </div>
              <Tag bordered={false}>{route.prompt}.j2</Tag>
            </header>
            <div className="route-candidates">
              {route.candidates.map((candidate, index) => (
                <div className="route-candidate" key={candidate.id}>
                  <span className="route-index">{String(index + 1).padStart(2, "0")}</span>
                  <div>
                    <strong>{candidate.provider}</strong>
                    <Text code>{candidate.model}</Text>
                  </div>
                  <Tag color={candidate.available ? "green" : "default"}>
                    {candidate.available ? "可用" : "缺少密钥"}
                  </Tag>
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
