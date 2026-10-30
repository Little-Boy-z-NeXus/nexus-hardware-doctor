import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { KeyboardMotorControl } from "./KeyboardMotorControl";

describe("KeyboardMotorControl", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockResolvedValue({ ok: true, json: async () => ({ status: "ok" }) });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("holds W for forward and sends an explicit stop on release", async () => {
    render(<KeyboardMotorControl enabled maxPwmPercent={80} defaultPwmPercent={50} />);
    fireEvent.keyDown(window, { key: "w" });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      action: "forward", pwm_percent: 50, hold_ms: 700,
    });
    expect(screen.getByText("Moving forward · release W to stop")).toBeInTheDocument();

    fireEvent.keyUp(window, { key: "w" });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(JSON.parse(fetchMock.mock.calls[1][1].body).action).toBe("stop");
  });

  it("maps S to reverse", async () => {
    render(<KeyboardMotorControl enabled maxPwmPercent={80} defaultPwmPercent={50} />);
    fireEvent.keyDown(window, { key: "S" });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).action).toBe("reverse");
  });

  it("does not capture W while the user is typing", () => {
    render(<><input aria-label="Tên" /><KeyboardMotorControl enabled maxPwmPercent={80} defaultPwmPercent={50} /></>);
    fireEvent.keyDown(screen.getByLabelText("Tên"), { key: "w" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("blocks motion when live safety checks are not ready", () => {
    render(<KeyboardMotorControl enabled={false} maxPwmPercent={80} defaultPwmPercent={50} disabledReason="Chưa an toàn" />);
    fireEvent.keyDown(window, { key: "w" });
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getAllByText("Chưa an toàn").length).toBeGreaterThan(0);
  });

  it("clamps the profile default to the hardware safety maximum", async () => {
    render(<KeyboardMotorControl enabled maxPwmPercent={40} defaultPwmPercent={50} />);
    fireEvent.keyDown(window, { key: "w" });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).pwm_percent).toBe(40);
  });
});
