import { test, expect, type WebSocketRoute } from "@playwright/test";
import fs from "node:fs/promises";

test("empty startup, precise edits, simulation, cameras and scene persistence", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByText("Simulation connected", { exact: true }),
  ).toBeVisible();
  await expect(page.locator("canvas")).toHaveCount(4);
  await expect(page.getByTestId("simulation-time")).toHaveText("0.00 s");
  await expect(
    page.getByText("Your tabletop is a blank canvas."),
  ).toBeVisible();
  await page.screenshot({ path: "test-results/startup.png" });
  await page
    .getByRole("button", { name: "Add Plastic cup", exact: true })
    .click();
  await expect(page.getByLabel("Object name", { exact: true })).toHaveValue(
    "Plastic cup",
  );
  await page.getByLabel("Position Z", { exact: true }).fill("1.1");
  await page.getByLabel("Position Z", { exact: true }).press("Enter");
  await expect(page.getByText("Updating scene…")).toHaveCount(0);
  await expect(page.getByLabel("Position Z", { exact: true })).toHaveValue(
    "1.1",
  );
  await page
    .getByRole("button", { name: "Step simulation", exact: true })
    .click();
  await expect(page.getByTestId("simulation-time")).toHaveText("0.02 s");
  await page.getByRole("button", { name: "Physics only", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Pause", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Mass (kg)", { exact: true })).toBeDisabled();
  await expect
    .poll(async () =>
      parseFloat(await page.getByTestId("simulation-time").innerText()),
    )
    .toBeGreaterThan(0.7);
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  await expect(page.getByLabel("Position Z", { exact: true })).toBeEnabled();
  expect(
    Number(await page.getByLabel("Position Z", { exact: true }).inputValue()),
  ).toBeLessThan(0.86);
  await page.getByLabel("Uniform scale", { exact: true }).fill("1.4");
  await page.getByLabel("Uniform scale", { exact: true }).press("Enter");
  await expect(
    page.getByText("101 × 101 × 140 mm", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Mass (kg)", { exact: true }).fill("0.06");
  await page.getByLabel("Mass (kg)", { exact: true }).press("Enter");
  await expect(page.getByText("Updating scene…")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Duplicate object", exact: true })
    .click();
  await expect(page.getByLabel("Object name", { exact: true })).toHaveValue(
    "Plastic cup copy",
  );
  await page
    .getByRole("button", { name: "Delete object", exact: true })
    .click();
  await expect(page.getByText("1 objects · 8 assets")).toBeVisible();
  await page.getByRole("button", { name: "Top view", exact: true }).click();
  await expect(page.locator("canvas")).toHaveCount(1);
  await page
    .getByRole("button", { name: "Reset top camera", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Toggle dual viewport", exact: true })
    .click();
  await expect(page.locator("canvas")).toHaveCount(4);
  const top = page.getByTestId("viewport-top");
  const box = (await top.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.wheel(0, -250);
  await expect
    .poll(() => page.evaluate(() => localStorage.getItem("so101.cameras")))
    .not.toBeNull();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Save scene", exact: true }).click();
  const download = await downloadPromise;
  const path = (await download.path())!;
  const doc = JSON.parse(await fs.readFile(path, "utf8"));
  expect(doc.scene.objects).toHaveLength(1);
  expect(doc.scene.objects[0].mass).toBe(0.06);
  const cameras = await page.evaluate(() =>
    localStorage.getItem("so101.cameras"),
  );
  await page.getByRole("button", { name: "Reset scene", exact: true }).click();
  await expect(
    page.getByText("Your tabletop is a blank canvas."),
  ).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("so101.cameras"))).toBe(
    cameras,
  );
  await page.getByTestId("scene-file").setInputFiles({
    name: "scene.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(doc)),
  });
  await expect(page.getByText("1 objects · 8 assets")).toBeVisible();
  await page.getByTestId("scene-file").setInputFiles({
    name: "bad.json",
    mimeType: "application/json",
    buffer: Buffer.from('{"version":99}'),
  });
  await expect(page.getByRole("alert")).toContainText("Not a supported");
  await expect(page.getByText("1 objects · 8 assets")).toBeVisible();
  expect(errors).toEqual([]);
});

test("drop placement in top viewport, joint edits, camera independence and keyboard", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByText("Simulation connected", { exact: true }),
  ).toBeVisible();
  await expect(page.locator("canvas")).toHaveCount(4);
  const top = page.getByTestId("viewport-top");
  const b = (await top.boundingBox())!;
  await page.getByTestId("asset-plate").dragTo(top, {
    targetPosition: { x: b.width * 0.6, y: b.height * 0.5 },
  });
  await expect(page.getByLabel("Object name", { exact: true })).toHaveValue(
    "Plastic plate",
  );
  const x = Number(
    await page.getByLabel("Position X", { exact: true }).inputValue(),
  );
  expect(x).toBeGreaterThan(0);
  expect(x).toBeLessThan(0.3);
  await page
    .getByRole("button", { name: "Frame selected object", exact: true })
    .click();
  await page.getByLabel("Rotation Z", { exact: true }).fill("35");
  await page.getByLabel("Rotation Z", { exact: true }).press("Enter");
  await expect(page.getByText("Updating scene…")).toHaveCount(0);
  await page
    .getByRole("button", { name: "SO-101 arm FIXED", exact: true })
    .click();
  const slider = page.getByLabel("shoulder_pan slider");
  await slider.focus();
  await slider.press("ArrowRight");
  await expect(page.getByText("Updating scene…")).toHaveCount(0);
  const topBefore = await page.evaluate(
    () => JSON.parse(localStorage.getItem("so101.cameras") || "{}").top,
  );
  const main = page.getByTestId("viewport-main");
  const m = (await main.boundingBox())!;
  await page.mouse.move(m.x + m.width * 0.45, m.y + m.height * 0.4);
  await page.mouse.down();
  await page.mouse.move(m.x + m.width * 0.52, m.y + m.height * 0.47, {
    steps: 10,
  });
  await page.mouse.up();
  await expect
    .poll(() =>
      page.evaluate(
        () => JSON.parse(localStorage.getItem("so101.cameras") || "{}").main,
      ),
    )
    .toBeTruthy();
  const topAfter = await page.evaluate(
    () => JSON.parse(localStorage.getItem("so101.cameras") || "{}").top,
  );
  expect(topAfter).toEqual(topBefore);
  await page.screenshot({ path: "test-results/robot-inspector.png" });
});

test("translate gizmo persists a drag and reconnect restores acknowledged work", async ({
  page,
}) => {
  let connection: WebSocketRoute | undefined;
  await page.routeWebSocket("**/ws*", (ws) => {
    connection = ws;
    ws.connectToServer();
  });
  await page.goto("/");
  await expect(
    page.getByText("Simulation connected", { exact: true }),
  ).toBeVisible();
  await expect(page.locator("canvas")).toHaveCount(4);
  await page
    .getByRole("button", { name: "Add Plastic cup", exact: true })
    .click();
  await expect(page.getByLabel("Object name", { exact: true })).toHaveValue(
    "Plastic cup",
  );
  await page.getByRole("button", { name: "Top view", exact: true }).click();
  const canvas = page.getByTestId("viewport-top").locator("canvas");
  await expect
    .poll(async () => (await canvas.boundingBox())?.width || 0)
    .toBeGreaterThan(600);
  const b = (await canvas.boundingBox())!;
  // Orthographic top projection: initial camera center at [0,0], 320 pixels/metre.
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );
  await page.screenshot({ path: "test-results/before-gizmo.png" });
  const cx = b.x + b.width / 2 + 0.08 * 320,
    cy = b.y + b.height / 2 + 0.1 * 320;
  await page.mouse.move(cx - 60, cy);
  await page.mouse.down();
  await page.mouse.move(cx - 10, cy, { steps: 12 });
  await page.mouse.up();
  await expect
    .poll(async () =>
      Number(await page.getByLabel("Position X", { exact: true }).inputValue()),
    )
    .toBeGreaterThan(0.15);
  const position = await page
    .getByLabel("Position X", { exact: true })
    .inputValue();
  await page.screenshot({ path: "test-results/gizmo.png" });
  await connection!.close({ code: 1001, reason: "Test transport disconnect" });
  await expect(
    page.getByText("Reconnecting · scene retained", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Simulation connected", { exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Position X", { exact: true })).toBeEnabled();
  await expect(page.getByLabel("Position X", { exact: true })).toHaveValue(
    position,
  );
  await page.getByLabel("Position X", { exact: true }).blur();
  await page.keyboard.press("Delete");
  await expect(
    page.getByText("Your tabletop is a blank canvas."),
  ).toBeVisible();
});

test("asset loading recovers from a transient server failure", async ({
  page,
}) => {
  let attempts = 0;
  await page.route("**/api/meshes", async (route) => {
    if (++attempts === 1)
      await route.fulfill({ status: 503, body: "temporarily unavailable" });
    else await route.continue();
  });
  await page.goto("/");
  await expect(page.locator("canvas")).toHaveCount(4, { timeout: 6000 });
  await expect(
    page.getByRole("button", { name: "Add Plastic cup", exact: true }),
  ).toBeEnabled();
});

test("native library drag and rotation gizmo work in the top view", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByText("Simulation connected", { exact: true }),
  ).toBeVisible();
  await expect(page.locator("canvas")).toHaveCount(4);
  await page.getByRole("button", { name: "Top view", exact: true }).click();
  const viewport = page.getByTestId("viewport-top");
  const canvas = viewport.locator("canvas");
  await expect
    .poll(async () => (await canvas.boundingBox())?.width || 0)
    .toBeGreaterThan(600);
  const b = (await canvas.boundingBox())!;
  await page.getByTestId("asset-spoon").dragTo(viewport, {
    targetPosition: { x: b.width / 2 + 65, y: b.height / 2 + 45 },
  });
  await expect(page.getByLabel("Object name", { exact: true })).toHaveValue(
    "Plastic spoon",
  );
  const x = Number(
    await page.getByLabel("Position X", { exact: true }).inputValue(),
  );
  const y = Number(
    await page.getByLabel("Position Y", { exact: true }).inputValue(),
  );
  expect(x).toBeCloseTo(65 / 320, 2);
  expect(y).toBeCloseTo(-45 / 320, 2);
  await page.getByRole("button", { name: "Rotate tool", exact: true }).click();
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );
  const cx = b.x + b.width / 2 + x * 320,
    cy = b.y + b.height / 2 - y * 320;
  const d = (b.height * 0.8) / 7 / Math.sqrt(2);
  await page.mouse.move(cx + d, cy - d);
  await page.mouse.down();
  await page.mouse.move(cx - d, cy - d, { steps: 16 });
  await page.mouse.up();
  await expect
    .poll(async () =>
      Math.abs(
        Number(
          await page.getByLabel("Rotation Z", { exact: true }).inputValue(),
        ),
      ),
    )
    .toBeGreaterThan(40);
  await page.screenshot({ path: "test-results/rotation.png" });
});

test("Save commits a focused draft and waits for server acknowledgement", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Add Plastic cup", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Add Plastic cup", exact: true })
    .click();
  const x = page.getByLabel("Position X", { exact: true });
  await expect(x).toBeEnabled();
  await x.fill("0.2");
  let downloading = page.waitForEvent("download");
  await page.getByRole("button", { name: "Save scene", exact: true }).click();
  let file = await downloading;
  expect(
    JSON.parse(await fs.readFile((await file.path())!, "utf8")).scene.objects[0]
      .position[0],
  ).toBe(0.2);
  await x.fill("0.25");
  downloading = page.waitForEvent("download");
  await x.press("ControlOrMeta+s");
  file = await downloading;
  expect(
    JSON.parse(await fs.readFile((await file.path())!, "utf8")).scene.objects[0]
      .position[0],
  ).toBe(0.25);
});

test("rejected numeric edit restores authoritative inspector value", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Add Plastic cup", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Add Plastic cup", exact: true })
    .click();
  const x = page.getByLabel("Position X", { exact: true });
  await expect(x).toBeEnabled();
  await x.fill("8");
  await x.press("Enter");
  await expect(page.getByRole("alert")).toContainText("within 5 m");
  await expect(x).toHaveValue("0.08");
});

test("failed reconnect preserves recoverable work and blocks simulation until reset", async ({
  page,
}) => {
  let session = 0,
    connection: WebSocketRoute | undefined;
  await page.routeWebSocket("**/ws*", (ws) => {
    connection = ws;
    const server = ws.connectToServer();
    const number = ++session;
    if (number === 2) {
      server.onMessage(() => {
        ws.send(
          JSON.stringify({
            type: "error",
            code: "session_missing",
            message: "Session lost after restart",
          }),
        );
        void ws.close({ code: 1008 });
      });
    }
    if (number > 2)
      ws.onMessage((message) => {
        const command = JSON.parse(String(message));
        if (command.type === "load")
          ws.send(
            JSON.stringify({
              type: "error",
              requestId: command.requestId,
              revision: 1,
              message: "Injected restore rejection",
            }),
          );
        else server.send(message);
      });
  });
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Add Plastic cup", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Add Plastic cup", exact: true })
    .click();
  await expect(page.getByLabel("Object name", { exact: true })).toHaveValue(
    "Plastic cup",
  );
  await connection!.close({ code: 1001 });
  await expect(page.getByRole("alert")).toContainText("restore");
  await expect(
    page.getByRole("button", { name: "Calculate path", exact: true }),
  ).toBeDisabled();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Save scene", exact: true }).click();
  const file = await downloadPromise;
  expect(
    JSON.parse(await fs.readFile((await file.path())!, "utf8")).scene.objects,
  ).toHaveLength(1);
  await page.getByRole("button", { name: "Reset scene", exact: true }).click();
  await expect(
    page.getByText("Your tabletop is a blank canvas."),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Calculate path", exact: true }),
  ).toBeEnabled();
});

test("camera actions are not replayed into another view or imported cameras", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Add Plastic cup", exact: true }),
  ).toBeEnabled();
  await expect(page.locator("canvas")).toHaveCount(4);
  await page
    .getByRole("button", { name: "Add Plastic cup", exact: true })
    .click();
  await expect(page.getByLabel("Object name", { exact: true })).toHaveValue(
    "Plastic cup",
  );
  await page
    .getByRole("button", { name: "Reset top camera", exact: true })
    .click();
  const before = await page.evaluate(
    () => JSON.parse(localStorage.getItem("so101.cameras")!).top,
  );
  await page
    .getByRole("button", { name: "Frame main camera", exact: true })
    .click();
  await page.getByRole("button", { name: "Top view", exact: true }).click();
  await expect
    .poll(
      async () =>
        (await page.getByTestId("viewport-top").locator("canvas").boundingBox())
          ?.width || 0,
    )
    .toBeGreaterThan(600);
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );
  expect(
    await page.evaluate(
      () => JSON.parse(localStorage.getItem("so101.cameras")!).top,
    ),
  ).toEqual(before);
  const d = page.waitForEvent("download");
  await page.getByRole("button", { name: "Save scene", exact: true }).click();
  const file = await d;
  const doc = JSON.parse(await fs.readFile((await file.path())!, "utf8"));
  doc.cameras.top = {
    position: [0.03, 0.02, 2.6],
    target: [0.03, 0.02, 0.75],
    zoom: 410,
  };
  await page.getByTestId("scene-file").setInputFiles({
    name: "view.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(doc)),
  });
  await expect(page.getByRole("status")).toContainText("Scene loaded");
  expect(
    await page.evaluate(
      () => JSON.parse(localStorage.getItem("so101.cameras")!).top,
    ),
  ).toMatchObject(doc.cameras.top);
});
