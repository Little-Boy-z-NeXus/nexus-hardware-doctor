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
    ["/dashboard", "Waiting for your hardware", "Dashboard"],
    ["/hardware", "Hardware Graph", "Hardware Graph"],
    ["/doctor", "AI Doctor", "AI Doctor"],
  ])("renders %s and marks its navigation item active", async (path, heading, navLabel) => {
    renderAt(path);

    expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: navLabel })).toHaveClass("nav-link--active");
  });

  it.each(["/", "/not-a-real-page"])("redirects %s to the dashboard", async (path) => {
    renderAt(path);

    expect(
      await screen.findByRole("heading", { level: 1, name: "Waiting for your hardware" }),
    ).toBeInTheDocument();
    expect(screen.getByText("nexus-demo-esp32")).toBeInTheDocument();
  });

  it("navigates from the dashboard to the hardware graph", async () => {
    const user = userEvent.setup();
    renderAt("/dashboard");

    await user.click(await screen.findByRole("link", { name: "Hardware Graph" }));

    expect(
      await screen.findByRole("heading", { level: 1, name: "Hardware Graph" }),
    ).toBeInTheDocument();
  });

  it("updates route SEO metadata without another network request", async () => {
    renderAt("/hardware");

    await screen.findByRole("heading", { level: 1, name: "Hardware Graph" });
    await waitFor(() => expect(document.title).toBe("Sơ đồ và log phần cứng | NeXus"));
    expect(document.documentElement.lang).toBe("vi");
  });
});
