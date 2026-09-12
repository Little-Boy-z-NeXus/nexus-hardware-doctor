import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { App } from "./App";

const TEST_HARDWARE_PROFILE = {
  schema_version: "1.0.0",
  profile_id: "nexus-profile-test",
  hardware_model_id: "nexus-test-runtime-model",
  name: "Test rig loaded from API",
  updated_at: "2026-09-13T00:00:00Z",
  controller: {
    family: "esp32",
    model: "Test ESP32-S3",
    board_id: "test-esp32-s3",
    runtime: "arduino",
    logic_voltage_v: 3.3,
    firmware_target: "nexus-test-esp32-s3",
  },
  transport: { type: "serial", baud_rate: 115200 },
  roles: {
    controller: "esp32",
    power_monitor: "ina226",
    motor_driver: "l298n",
    actuator: "motor",
    power: "power",
  },
  components: [
    { component_id: "esp32", component_type: "controller", model: "Test ESP32-S3", capabilities: [], pins: [] },
    {
      component_id: "ina226",
      component_type: "power_monitor",
      model: "INA226 R100 từ profile",
      address: "0x40",
      capabilities: [],
      pins: [],
    },
    { component_id: "l298n", component_type: "motor_driver", model: "Test L298N", capabilities: [], pins: [] },
    { component_id: "motor", component_type: "actuator", model: "Test JGB37", capabilities: [], pins: [] },
    { component_id: "power", component_type: "power_supply", model: "Test 12V supply", capabilities: [], pins: [] },
  ],
  connections: [
    {
      connection_id: "encoder_a",
      signal_type: "digital",
      wire_color: "yellow",
      from: { component_id: "motor", pin_id: "encoder_a" },
      to: { component_id: "esp32", pin_id: "gpio_16" },
    },
    {
      connection_id: "encoder_b",
      signal_type: "digital",
      wire_color: "green",
      from: { component_id: "motor", pin_id: "encoder_b" },
      to: { component_id: "esp32", pin_id: "gpio_17" },
    },
  ],
  capabilities: ["telemetry.publish"],
  telemetry: {
    interval_ms: 1000,
    measurements: [
      { field: "bus_voltage_v", metric_id: "power.bus_voltage", component_id: "ina226", unit: "V", nullable: false },
      { field: "current_ma", metric_id: "power.current", component_id: "ina226", unit: "mA", nullable: false },
      { field: "power_mw", metric_id: "power.power", component_id: "ina226", unit: "mW", nullable: false },
    ],
  },
  safety: {
    min_bus_voltage_v: 9.5,
    max_bus_voltage_v: 13,
    max_current_ma: 1500,
    max_pwm_percent: 80,
    max_motor_test_duration_ms: 3000,
    emergency_stop: "Stop test hardware",
  },
  firmware: {
    profile_version: "1.0.0",
    sensor_profile: "test-sensor",
    driver_profile: "test-driver",
    default_motor_test_pwm_percent: 20,
    pins: { i2c_sda: 1, i2c_scl: 2, motor_enable: 12, motor_in1: 13, motor_in2: 14, encoder_a: 16, encoder_b: 17 },
    sensor: { i2c_address: "0x40" },
  },
};

const TEST_LIVE_SNAPSHOT = {
  connection: {
    status: "connected",
    port: "COM-TEST",
    baud_rate: 115200,
    last_seen_at: "2026-09-13T00:00:00Z",
    log_file: "logs/test.ndjson",
    message: "Runtime snapshot from test API",
  },
  telemetry: {
    schema_version: "1.0.0",
    device_id: "nexus-live-from-board",
    hardware_model_id: "nexus-test-runtime-model",
    sample_id: "nexus-live-from-board-42",
    recorded_at: null,
    sequence: 42,
    measurements: {
      bus_voltage_v: 12.16,
      current_ma: 81.2,
      power_mw: 987.4,
      pwm_percent: 0,
      driver_enabled: false,
      motor_rpm: null,
    },
    quality: { signal_quality_percent: 99, source: "device" },
  },
  logs: [],
  diagnostics: [],
  health: { status: "healthy", active_issue_count: 0 },
  signal_health: {
    monitor_ready: true,
    i2c_verified: true,
    encoder_a_verified: false,
    encoder_b_verified: false,
    last_i2c_verified_at: "2026-09-13T00:00:00Z",
    last_encoder_verified_at: null,
  },
  compatibility: {
    expected_profile_id: "nexus-profile-test",
    reported_profile_id: "nexus-profile-test",
    expected_profile_sha256: "test-sha",
    reported_profile_sha256: "test-sha",
    expected_hardware_model_id: "nexus-test-runtime-model",
    reported_hardware_model_id: "nexus-test-runtime-model",
    firmware_profile_version: "1.0.0",
    firmware_profile_verified: true,
    sensor_identity_verified: true,
    last_verified_at: "2026-09-13T00:00:00Z",
  },
  hardware: {
    profile_id: "nexus-profile-test",
    profile_schema_version: "1.0.0",
    profile_sha256: "test-sha",
    hardware_model_id: "nexus-test-runtime-model",
    controller: "Test ESP32-S3",
    sensor: "INA226 R100 từ profile",
    driver: "Test L298N",
    motor: "Test JGB37",
    power: "Test 12V supply",
    capabilities: ["telemetry.publish"],
    limits: { min_bus_voltage_v: 9.5, max_bus_voltage_v: 13, max_current_ma: 1500, max_pwm_percent: 80 },
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
      if (url.endsWith("/api/v1/live")) {
        return new Response(JSON.stringify(TEST_LIVE_SNAPSHOT), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.endsWith("/api/diagnosis/capabilities")) {
        return new Response(JSON.stringify({
          live_enabled: true,
          live_configured: true,
          physical_commands_enabled: false,
          serial_reads_enabled: true,
          serial_device_id: "nexus-live-from-board",
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.endsWith("/api/devices/nexus-live-from-board/diagnoses")) {
        return new Response(JSON.stringify({
          session_id: "runtime-session-id",
          result: {
            status: "diagnosed",
            summary: "Runtime diagnosis complete",
            plan: {
              confidence: 0.91,
              user_message: "Nemotron đã đọc mẫu #42 từ thiết bị thật.",
              stop_condition: "diagnosed",
              hypotheses: [{
                id: "normal",
                label: "Điện áp đang ổn định",
                confidence: 0.91,
                evidence_ids: ["nexus-live-from-board-42"],
              }],
            },
            observations: [{ evidence_id: "observation-42", tool_name: "get_telemetry", status: "succeeded" }],
            model_runtime: { provider: "nebius", calls: [{ response_model: "test-nemotron" }] },
            physical_commands_enabled: false,
          },
        }), { status: 200, headers: { "Content-Type": "application/json" } });
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
    ["/dashboard", "Hệ thống đang ổn định", "Tổng quan"],
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
      await screen.findByRole("heading", { level: 1, name: "Hệ thống đang ổn định" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("nexus-live-from-board")).toBeInTheDocument();
  });

  it("navigates from the dashboard to the hardware graph", async () => {
    const user = userEvent.setup();
    renderAt("/dashboard");

    await user.click(await screen.findByRole("link", { name: "Sơ đồ phần cứng" }));

    expect(
      await screen.findByRole("heading", { level: 1, name: "Sơ đồ phần cứng" }),
    ).toBeInTheDocument();
  });

  it("renders a real backend diagnosis instead of a browser-generated answer", async () => {
    const user = userEvent.setup();
    renderAt("/doctor");

    const input = await screen.findByRole("textbox", { name: "Hỏi Bác sĩ AI" });
    await user.type(input, "Motor có an toàn không?");
    await user.click(screen.getByRole("button", { name: "Gửi câu hỏi" }));

    expect(screen.getByText("Motor có an toàn không?")).toBeInTheDocument();
    expect(await screen.findAllByText("Nemotron đã đọc mẫu #42 từ thiết bị thật.")).toHaveLength(2);
    expect(screen.getByText(/nebius\/test-nemotron/)).toBeInTheDocument();
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
    expect(await screen.findByText("Dây vàng → GPIO16")).toBeInTheDocument();
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
      screen.getByText("INA226 R100 từ profile đã khớp identity khai báo trong profile."),
    ).toBeInTheDocument();
  });

  it("keeps long component names accessible in a horizontally scrollable BOM", async () => {
    renderAt("/hardware");

    const flow = await screen.findByTestId("hardware-flow-scroll");
    expect(flow).toHaveAttribute("tabindex", "0");
    expect(flow).toHaveAccessibleName("Chuỗi 5 thành phần phần cứng. Có thể cuộn ngang để xem đầy đủ.");
    expect(
      screen.getByTitle("INA226 R100 từ profile"),
    ).toHaveTextContent("INA226 R100 từ profile");
    expect(screen.getByTitle("Test 12V supply")).toBeInTheDocument();
  });
});
