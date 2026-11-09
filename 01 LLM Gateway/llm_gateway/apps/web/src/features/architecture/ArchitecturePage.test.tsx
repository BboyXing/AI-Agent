import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { App } from "../../app/App";

describe("ArchitecturePage", () => {
  it("is reachable from the left navigation and exposes stage details", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/architecture"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "架构全流程" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /架构/ })).toHaveAttribute(
      "aria-current",
      "page",
    );

    const providerStage = screen
      .getAllByRole("button", { name: /供应商适配与降级/ })
      .at(0);
    expect(providerStage).toBeDefined();
    await user.click(providerStage!);

    expect(
      screen.getByText("流式响应在首个可见 chunk 前允许切换候选"),
    ).toBeInTheDocument();
  });
});
