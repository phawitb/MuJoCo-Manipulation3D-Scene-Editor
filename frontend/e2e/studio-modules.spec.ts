import { test, expect } from "@playwright/test";
test("tabs preserve Gym and hidden Gym does not handle keyboard shortcuts", async ({
  page,
  request,
}) => {
  const packet = await (await request.post("/api/sessions")).json();
  try {
    await page.goto(`/?session=${packet.sessionId}`);
    await expect(
      page.getByRole("tab", { name: "Gym", exact: true }),
    ).toHaveAttribute("aria-selected", "true");
    await expect(
      page.getByText("Simulation connected", { exact: false }),
    ).toBeVisible();
    await page.getByRole("tab", { name: "Setting Connection" }).click();
    await expect(
      page.getByRole("heading", { name: "Setting Connection" }),
    ).toBeVisible();
    await page.getByRole("heading", { name: "Setting Connection" }).click();
    await page.keyboard.press("Space");
    expect(
      (await (await request.get(`/api/sessions/${packet.sessionId}`)).json())
        .running,
    ).toBe(false);
    await page.getByRole("tab", { name: "Blender", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Blender", exact: true }),
    ).toBeVisible();
    await page.getByRole("tab", { name: "Gym", exact: true }).click();
    await expect(page.getByTestId("session-id")).toBeVisible();
    await page.getByRole("tab", { name: "Setting Connection" }).click();
    await page.reload();
    await expect(
      page.getByRole("tab", { name: "Setting Connection" }),
    ).toHaveAttribute("aria-selected", "true");
  } finally {
    await request.delete(`/api/sessions/${packet.sessionId}`);
  }
});

test("connection verifies status, blocks unmapped motion and persists camera choices through API", async ({
  page,
  request,
}) => {
  const packet = await (await request.post("/api/sessions")).json();
  let calls: string[] = [];
  let settings = {
    assignments: {
      back: null as number | null,
      front: null as number | null,
      wrist: null as number | null,
    },
  };
  const state = {
    connected: true,
    port: "/dev/cu.test",
    identity: "test-device",
    owner_session_id: packet.sessionId,
    enabled: false,
    sync_mode: "off",
    fault: null,
    calibrated: false,
    calibration: null,
    telemetry_age_s: 0.02,
    telemetry: [
      {
        id: 1,
        name: "shoulder_pan",
        raw: 2048,
        model: 777,
        voltage: 12,
        temperature: 30,
        torque: false,
      },
    ],
    lease_remaining_s: 0,
    target_rad: null,
  };
  await page.route("**/api/connection/**", async (route) => {
    const p = new URL(route.request().url()).pathname;
    calls.push(p);
    let result: unknown = state;
    if (p.endsWith("/ports"))
      result = { ports: [{ port: "/dev/cu.test", description: "Test SO101" }] };
    if (p.endsWith("/settings")) result = settings;
    if (p.endsWith("/cameras/assignments")) {
      settings = { assignments: route.request().postDataJSON() };
      result = settings;
    }
    await route.fulfill({ json: result });
  });
  try {
    await page.goto(`/?session=${packet.sessionId}`);
    await page.getByRole("tab", { name: "Setting Connection" }).click();
    await expect(
      page.getByText("Joint mapping required before movement"),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Enable at current pose" }),
    ).toBeDisabled();
    await page.getByRole("button", { name: "Edit joint mapping" }).click();
    await expect(
      page.getByRole("button", { name: "Save verified mapping" }),
    ).toBeDisabled();
    await page.getByLabel("back camera idx").fill("0");
    await page.getByLabel("front camera idx").fill("1");
    await page.getByLabel("wrist camera idx").fill("2");
    await page.getByRole("button", { name: "Save camera setup" }).click();
    await expect(
      page.getByText("Camera assignments saved.", { exact: false }),
    ).toBeVisible();
    expect(settings.assignments).toEqual({ back: 0, front: 1, wrist: 2 });
    expect(calls.some((p) => p.endsWith("/enable"))).toBe(false);
    await page.getByRole("button", { name: "Edit joint mapping" }).click();
    await page.screenshot({
      path: "/tmp/connected-settings-ui.png",
      fullPage: true,
    });
  } finally {
    await request.delete(`/api/sessions/${packet.sessionId}`);
  }
});

test("hiding the browser stops physical streaming and does not renew heartbeat", async ({
  page,
  request,
}) => {
  const packet = await (await request.post("/api/sessions")).json();
  let stops = 0,
    beats = 0;
  const state = {
    connected: true,
    port: "/dev/cu.test",
    identity: "test",
    owner_session_id: packet.sessionId,
    enabled: true,
    sync_mode: "gym_to_real",
    fault: null,
    calibrated: true,
    calibration: null,
    telemetry_age_s: 0.01,
    telemetry: [],
    lease_remaining_s: 3,
    target_rad: [],
  };
  await page.route("**/api/connection/**", async (route) => {
    const p = new URL(route.request().url()).pathname;
    let result: unknown = state;
    if (p.endsWith("/ports")) result = { ports: [] };
    if (p.endsWith("/settings"))
      result = { assignments: { back: null, front: null, wrist: null } };
    if (p.endsWith("/stop")) {
      stops++;
      state.enabled = false;
      state.sync_mode = "off";
    }
    if (p.endsWith("/heartbeat")) beats++;
    await route.fulfill({ json: result });
  });
  try {
    await page.goto(`/?session=${packet.sessionId}`);
    await page.getByRole("tab", { name: "Setting Connection" }).click();
    await expect(
      page.getByRole("button", { name: "Real arm · Stop & hold" }),
    ).toBeVisible();
    await page.evaluate(() => {
      Object.defineProperty(document, "visibilityState", {
        configurable: true,
        value: "hidden",
      });
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await expect.poll(() => stops).toBe(1);
    const previous = beats;
    await page.waitForTimeout(1500);
    expect(beats).toBe(previous);
    await expect(
      page.getByRole("button", { name: "Real arm · Stop & hold" }),
    ).not.toBeVisible();
  } finally {
    await request.delete(`/api/sessions/${packet.sessionId}`);
  }
});

test("reloaded connection can explicitly select its existing owner without auto-renewing motion", async ({
  page,
  request,
}) => {
  const packet = await (await request.post("/api/sessions")).json();
  let beats = 0;
  const state = {
    connected: true,
    port: "/dev/cu.test",
    identity: "test",
    owner_session_id: packet.sessionId,
    enabled: false,
    sync_mode: "off",
    fault: null,
    calibrated: false,
    calibration: null,
    telemetry_age_s: 0.01,
    telemetry: [],
    lease_remaining_s: 0,
    target_rad: null,
  };
  await page.route("**/api/connection/**", async (route) => {
    const p = new URL(route.request().url()).pathname;
    let result: unknown = state;
    if (p.endsWith("/ports")) result = { ports: [] };
    if (p.endsWith("/settings"))
      result = { assignments: { back: null, front: null, wrist: null } };
    if (p.endsWith("/heartbeat")) beats++;
    await route.fulfill({ json: result });
  });
  try {
    await page.addInitScript(() =>
      localStorage.setItem("studio.activeTab", "connection"),
    );
    await page.goto("/");
    await expect(
      page.getByText("Joint mapping required before movement"),
    ).toBeVisible();
    expect(beats).toBe(0);
    await expect(page.getByLabel("Hardware Gym session")).toBeEnabled();
    await page
      .getByLabel("Hardware Gym session")
      .selectOption(packet.sessionId);
    await expect(
      page.getByRole("button", { name: "Edit joint mapping" }),
    ).toBeEnabled();
    await expect(
      page.getByRole("button", { name: "Disconnect", exact: true }),
    ).toBeEnabled();
  } finally {
    await request.delete(`/api/sessions/${packet.sessionId}`);
  }
});
