import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { App } from "./App";

const TEST_HARDWARE_PROFILE = {
  profile_id: "nexus-profile-test",
  roles: {
    controller: "esp32",
    power_monitor: "ina226",
    motor_driver: "l298n",
    actuator: "motor",
    power: "power",
  },
  components: [
    { component_id: "esp32", component_type: "controller", model: "Test ESP32-S3" },
    {
      component_id: "ina226",
      component_type: "power_monitor",
      model: "INA226 R100 từ profile",
      address: "0x40",
    },
    { component_id: "l298n", component_type: "motor_driver", model: "Test L298N" },
    { component_id: "motor", component_type: "actuator", model: "Test JGB37" },
    { component_id: "power", component_type: "power_supply", model: "Test 12V supply" },
  ],
  firmware: {
    pins: { i2c_sda: 1, i2c_scl: 2, encoder_a: 16, encoder_b: 17 },
    sensor: { i2c_address: "0x40" },
  },
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/v1/hardware-profile")) {
        return new Response(JSON.stringify(TEST_HARDWARE_PROFILE), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ detail: "Test backend offline" }), {
        status: 503,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

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

  it("does not claim idle encoder wires are healthy before a supervised motor run", async () => {
    renderAt("/hardware");

    expect(await screen.findByRole("heading", { name: "Tình trạng dây tín hiệu" })).toBeInTheDocument();
    expect(screen.getByText("Dây vàng → GPIO16")).toBeInTheDocument();
    expect(screen.getByText("Dây xanh lá → GPIO17")).toBeInTheDocument();
    expect(
      screen.getAllByText("Chỉ kiểm chứng được khi motor chạy trong bài test có giám sát."),
    ).toHaveLength(2);
  });

  it("shows separate firmware and physical sensor identity checks", async () => {
    renderAt("/hardware");

    expect(
      await screen.findByRole("heading", { name: "Đối chiếu firmware với BOM" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Firmware")).toBeInTheDocument();
    expect(await screen.findByText("INA226 R100 từ profile · 0x40")).toBeInTheDocument();
    expect(
      screen.getByText("Chờ đọc identity; INA219 hoặc module gắn nhầm sẽ bị chặn tại đây."),
    ).toBeInTheDocument();
  });
});
