import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { App } from "./App";

afterEach(cleanup);

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe("NeXus application routes", () => {
  it.each([
    ["/dashboard", "Đang chờ phần cứng", "Tổng quan"],
    ["/hardware", "Sơ đồ phần cứng", "Sơ đồ phần cứng"],
    ["/doctor", "Bác sĩ AI", "Bác sĩ AI"],
  ])("renders %s and marks its navigation item active", async (path, heading, navLabel) => {
    renderAt(path);

    expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: navLabel })).toHaveClass("nav-link--active");
  });

  it.each(["/", "/not-a-real-page"])("redirects %s to the dashboard", async (path) => {
    renderAt(path);

    expect(
      await screen.findByRole("heading", { level: 1, name: "Đang chờ phần cứng" }),
    ).toBeInTheDocument();
    expect(screen.getByText("nexus-demo-esp32")).toBeInTheDocument();
  });

  it("navigates from the dashboard to the hardware graph", async () => {
    const user = userEvent.setup();
    renderAt("/dashboard");

    await user.click(await screen.findByRole("link", { name: "Sơ đồ phần cứng" }));

    expect(
      await screen.findByRole("heading", { level: 1, name: "Sơ đồ phần cứng" }),
    ).toBeInTheDocument();
  });

  it("answers a Vietnamese diagnosis question from the current realtime state", async () => {
    const user = userEvent.setup();
    renderAt("/doctor");

    const input = await screen.findByRole("textbox", { name: "Hỏi Bác sĩ AI" });
    await user.type(input, "Motor có an toàn không?");
    await user.click(screen.getByRole("button", { name: "Gửi câu hỏi" }));

    expect(screen.getByText("Motor có an toàn không?")).toBeInTheDocument();
    expect(screen.getByText(/Tôi chưa có telemetry trực tiếp/)).toBeInTheDocument();
  });

  it("updates route SEO metadata without another network request", async () => {
    renderAt("/hardware");

    await screen.findByRole("heading", { level: 1, name: "Sơ đồ phần cứng" });
    await waitFor(() => expect(document.title).toBe("Sơ đồ và log phần cứng | NeXus"));
    expect(document.documentElement.lang).toBe("vi");
  });
});
