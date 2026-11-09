import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfigProvider } from "antd";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GatewaySessionProvider } from "../../app/session";
import { ChatPage } from "./ChatPage";

beforeEach(() => {
  window.sessionStorage.setItem("llm_gateway_api_key", "test-key");
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      Response.json({
        object: "list",
        data: [
          {
            id: "default",
            object: "model",
            created: 0,
            owned_by: "llm-gateway",
            prompt: "default",
            candidates: [
              {
                id: "deepseek-chat",
                provider: "deepseek",
                model: "deepseek-chat",
                available: true,
              },
            ],
          },
        ],
      }),
    ),
  );
});

describe("ChatPage", () => {
  it("uses the default route and exposes both API modes", async () => {
    const user = userEvent.setup();
    render(
      <ConfigProvider>
        <GatewaySessionProvider>
          <ChatPage />
        </GatewaySessionProvider>
      </ConfigProvider>,
    );

    expect(await screen.findByText("deepseek-chat")).toBeInTheDocument();
    expect(screen.getAllByText("default").length).toBeGreaterThan(0);

    await user.click(screen.getByText("Responses"));
    const composer = screen.getByPlaceholderText("输入问题，Enter 发送，Shift + Enter 换行");
    await user.type(composer, "hello");
    expect(screen.getByRole("button", { name: "发送请求" })).toBeEnabled();
  });
});
