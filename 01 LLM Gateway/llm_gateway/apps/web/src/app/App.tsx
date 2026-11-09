import { lazy, Suspense, useState } from "react";
import {
  App as AntApp,
  Button,
  ConfigProvider,
  Input,
  Modal,
  Spin,
  Tag,
  Typography,
} from "antd";
import zhCN from "antd/locale/zh_CN";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { GatewaySessionProvider, useGatewaySession } from "./session";

const { Text } = Typography;

const navigation = [
  { to: "/architecture", label: "架构", index: "00" },
  { to: "/", label: "对话", index: "01" },
  { to: "/models", label: "模型", index: "02" },
  { to: "/usage", label: "用量", index: "03" },
];

const ArchitecturePage = lazy(() =>
  import("../features/architecture/ArchitecturePage").then((module) => ({
    default: module.ArchitecturePage,
  })),
);
const ChatPage = lazy(() =>
  import("../features/chat/ChatPage").then((module) => ({ default: module.ChatPage })),
);
const ModelsPage = lazy(() =>
  import("../features/models/ModelsPage").then((module) => ({
    default: module.ModelsPage,
  })),
);
const UsagePage = lazy(() =>
  import("../features/usage/UsagePage").then((module) => ({
    default: module.UsagePage,
  })),
);

export function App() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: "#bd4b2c",
          colorInfo: "#355e50",
          colorBgBase: "#f3f0e8",
          colorTextBase: "#18211d",
          colorBorder: "#d5d0c4",
          borderRadius: 4,
          fontFamily:
            '"Avenir Next", "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
        },
        components: {
          Button: { borderRadius: 2, fontWeight: 600 },
          Input: { borderRadius: 2 },
          Select: { borderRadius: 2 },
          Segmented: { borderRadius: 2 },
          Table: { headerBg: "#ebe6db", rowHoverBg: "#f8f5ed" },
        },
      }}
    >
      <AntApp>
        <GatewaySessionProvider>
          <BrowserApp />
        </GatewaySessionProvider>
      </AntApp>
    </ConfigProvider>
  );
}

function BrowserApp() {
  const location = useLocation();
  const { apiKey, setApiKey } = useGatewaySession();
  const [keyOpen, setKeyOpen] = useState(false);
  const [keyDraft, setKeyDraft] = useState(apiKey ?? "");
  const active = navigation.find((item) => item.to === location.pathname) ?? navigation[0];

  const openKeyDialog = () => {
    setKeyDraft(apiKey ?? "");
    setKeyOpen(true);
  };

  return (
    <div className="app-shell">
      <aside className="app-nav">
        <div className="brand-lockup">
          <span className="brand-mark">O</span>
          <div>
            <strong>ORBIT</strong>
            <small>LLM GATEWAY</small>
          </div>
        </div>

        <nav aria-label="主导航">
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}
            >
              <span>{item.index}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="connection-card">
          <span className={apiKey ? "connection-dot online" : "connection-dot"} />
          <div>
            <strong>{apiKey ? "网关已连接" : "等待连接"}</strong>
            <small>{apiKey ? "Bearer key · 当前会话" : "需要 API Key"}</small>
          </div>
          <Button type="text" size="small" onClick={openKeyDialog}>
            {apiKey ? "更换" : "连接"}
          </Button>
        </div>
      </aside>

      <div className="app-main">
        <header className="topbar">
          <div>
            <span className="topbar-kicker">{active.index}</span>
            <Text>{active.label}</Text>
          </div>
          <div className="topbar-status">
            <Tag bordered={false}>TEXT ONLY</Tag>
            <Tag bordered={false} color={apiKey ? "green" : "default"}>
              {apiKey ? "READY" : "OFFLINE"}
            </Tag>
          </div>
        </header>

        <main className="content-area">
          <Suspense
            fallback={
              <div className="route-loading">
                <Spin />
              </div>
            }
          >
            <Routes>
              <Route path="/architecture" element={<ArchitecturePage />} />
              <Route path="/" element={<ChatPage />} />
              <Route path="/models" element={<ModelsPage />} />
              <Route path="/usage" element={<UsagePage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </main>
      </div>

      <Modal
        title="连接 LLM Gateway"
        open={keyOpen}
        okText="保存到当前会话"
        cancelText="取消"
        onOk={() => {
          setApiKey(keyDraft);
          setKeyOpen(false);
        }}
        onCancel={() => setKeyOpen(false)}
      >
        <div className="key-dialog-copy">
          <p>
            API Key 仅写入 <code>sessionStorage</code>，关闭当前标签页后失效。
          </p>
          <Input.Password
            value={keyDraft}
            onChange={(event) => setKeyDraft(event.target.value)}
            placeholder="输入后端 identity.api_keys 中的密钥"
            autoFocus
          />
        </div>
      </Modal>
    </div>
  );
}
