import { test, expect } from "@playwright/test";

test("task workbench exposes cameras and performs spoon to cup", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByText("Simulation connected", { exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("viewport-wrist")).toBeVisible();
  await expect(page.getByTestId("viewport-front")).toBeVisible();
  await page.getByRole("button", { name: "Load task example" }).click();
  await expect(page.getByTestId("object-spoon")).toBeVisible();
  await page
    .getByRole("button", { name: "Calculate path", exact: true })
    .click();
  await expect(page.getByTestId("plan-status")).toContainText("Path ready");
  await page
    .getByRole("button", { name: "Run simulation", exact: true })
    .click();
  await expect(page.getByTestId("task-status")).toContainText("Complete", {
    timeout: 45000,
  });
  await expect(page.getByTestId("task-message")).toContainText(
    "released and settled",
  );
  await page.screenshot({ path: "../docs/screenshots/pick-place-success.png" });
});

test("scene selection sets task and front camera is editable", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByText("Simulation connected", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Add IKEA KALAS spoon", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Add IKEA KALAS cup", exact: true })
    .click();
  await page.getByRole("button", { name: "Choose pick object" }).click();
  await page.locator('[data-testid^="object-kalas_spoon_"]').click();
  await page.locator('[data-testid^="object-kalas_cup_"]').click();
  await expect(page.getByTestId("task-instruction")).toContainText(
    "IKEA KALAS spoon",
  );
  await expect(page.getByTestId("task-instruction")).toContainText(
    "IKEA KALAS cup",
  );
  await page.getByRole("button", { name: "Edit front camera" }).click();
  await page.getByLabel("Camera position X").fill("0.8");
  await page.getByRole("button", { name: "Apply camera" }).click();
  await expect(
    page.getByRole("dialog", { name: "Edit camera" }),
  ).not.toBeVisible();
  const sid = await page
    .getByTestId("session-id")
    .getAttribute("data-session-id");
  const state = await (await page.request.get(`/api/sessions/${sid}`)).json();
  expect(state.scene.cameras.front.position[0]).toBe(0.8);
});

test("import a local mesh, edit it, save and reload", async ({ page }) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Import object STL · OBJ · GLB" })
    .click();
  const obj =
    "v -1 -1 -1\nv 1 -1 -1\nv 1 1 -1\nv -1 1 -1\nv -1 -1 1\nv 1 -1 1\nv 1 1 1\nv -1 1 1\nf 1 3 2\nf 1 4 3\nf 5 6 7\nf 5 7 8\nf 1 2 6\nf 1 6 5\nf 2 3 7\nf 2 7 6\nf 3 4 8\nf 3 8 7\nf 4 1 5\nf 4 5 8\n";
  await page.getByTestId("object-file").setInputFiles({
    name: "local-block.obj",
    mimeType: "text/plain",
    buffer: Buffer.from(obj),
  });
  await page.getByLabel("Object longest side").fill("60");
  await page.getByRole("button", { name: "Import and place" }).click();
  await expect(page.getByLabel("Object name", { exact: true })).toHaveValue(
    "local-block",
  );
  await page.getByLabel("Mass (kg)", { exact: true }).fill("0.08");
  await page.getByLabel("Mass (kg)", { exact: true }).press("Enter");
  const downloading = page.waitForEvent("download");
  await page.getByRole("button", { name: "Save scene", exact: true }).click();
  const file = await downloading;
  const fs = await import("node:fs/promises");
  const doc = JSON.parse(await fs.readFile((await file.path())!, "utf8"));
  expect(doc.scene.objects[0].asset).toBe("mesh");
  expect(doc.scene.objects[0].mass).toBe(0.08);
  expect(doc.scene.objects[0].mesh.faces.length).toBe(36);
  await page.getByRole("button", { name: "Reset scene", exact: true }).click();
  await expect(
    page.getByText("Your tabletop is a blank canvas."),
  ).toBeVisible();
  await page.getByTestId("scene-file").setInputFiles({
    name: "mesh-scene.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(doc)),
  });
  await expect(
    page.getByRole("button", { name: "local-block", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "local-block", exact: true }).click();
  await expect(page.getByLabel("Mass (kg)", { exact: true })).toHaveValue(
    "0.08",
  );
});

test("pick and destination can be selected directly on the 3D scene", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Load task example" }).click();
  await expect(page.getByTestId("object-spoon")).toBeVisible();
  const sid = await page
    .getByTestId("session-id")
    .getAttribute("data-session-id");
  await page.request.post(`/api/sessions/${sid}/command`, {
    data: { type: "task", source: null, target: null },
  });
  await expect(page.getByTestId("task-instruction")).toContainText(
    "Click an object",
  );
  await page.getByRole("button", { name: "Top view", exact: true }).click();
  await page.getByRole("button", { name: "Choose pick object" }).click();
  await expect
    .poll(
      async () =>
        (await page.getByTestId("viewport-top").locator("canvas").boundingBox())
          ?.width || 0,
    )
    .toBeGreaterThan(600);
  const box = (await page
    .getByTestId("viewport-top")
    .locator("canvas")
    .boundingBox())!;
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );
  await page.mouse.click(
    box.x + box.width / 2 + 0.07 * 320,
    box.y + box.height / 2 + 0.13 * 320,
  );
  await expect(page.getByTestId("task-instruction")).toContainText(
    "Pick · KALAS spoon",
  );
  await expect(
    page.getByRole("button", { name: "Choose place object" }),
  ).toBeEnabled();
  await page.mouse.click(
    box.x + box.width / 2 - 0.09 * 320,
    box.y + box.height / 2 + 0.04 * 320,
  );
  await expect(page.getByTestId("task-instruction")).toContainText(
    "Place · KALAS cup",
  );
  const state = await (await page.request.get(`/api/sessions/${sid}`)).json();
  expect(state.scene.task).toEqual({ source: "spoon", target: "cup" });
});

test("external API edits are reflected in the browser and pause freezes the task", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByText("Simulation connected", { exact: true }),
  ).toBeVisible();
  const sid = await page
    .getByTestId("session-id")
    .getAttribute("data-session-id");
  const command = (data: object) =>
    page.request.post(`/api/sessions/${sid}/command`, { data });
  await command({ type: "example" });
  await expect(page.getByTestId("object-spoon")).toBeVisible();
  const before = await (await page.request.get(`/api/sessions/${sid}`)).json();
  await command({ type: "plan" });
  await expect(page.getByTestId("plan-status")).toContainText("Path ready");
  await command({ type: "run" });
  await expect(
    page.getByRole("button", { name: "Pause", exact: true }),
  ).toBeVisible();
  await expect
    .poll(async () =>
      parseFloat(await page.getByTestId("simulation-time").innerText()),
    )
    .toBeGreaterThan(0.5);
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  const paused = await (await page.request.get(`/api/sessions/${sid}`)).json();
  expect(paused.cameras.wrist.position).not.toEqual(
    before.cameras.wrist.position,
  );
  await expect(page.getByTestId("task-status")).toContainText("Paused");
  await command({ type: "snapshot" });
  expect(
    (await (await page.request.get(`/api/sessions/${sid}`)).json()).time,
  ).toBe(paused.time);
  await command({
    type: "camera",
    camera: "front",
    value: {
      position: [0.8, -0.9, 1.4],
      target: [0, 0, 0.8],
      zoom: 1,
      fov: 55,
    },
  });
  await page.getByRole("button", { name: "Edit front camera" }).click();
  await expect(page.getByLabel("Camera position X")).toHaveValue("0.8");
  await page.getByRole("button", { name: "Close camera editor" }).click();
  await page.getByRole("button", { name: "Stop task" }).click();
  await expect(page.getByTestId("task-status")).toHaveText("Stopped");
});

test("narrow window keeps task, cameras and object controls usable", async ({
  page,
}) => {
  await page.setViewportSize({ width: 480, height: 840 });
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Load task example" }),
  ).toBeVisible();
  await expect(page.getByTestId("viewport-wrist")).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(480);
  await page.getByRole("button", { name: "Objects", exact: true }).click();
  await page
    .getByRole("button", { name: "Add IKEA KALAS cup", exact: true })
    .click();
  await page.getByRole("button", { name: "Inspector", exact: true }).click();
  await expect(page.getByLabel("Object name", { exact: true })).toHaveValue(
    "IKEA KALAS cup",
  );
  await page.getByRole("button", { name: "Inspector", exact: true }).click();
  await page.screenshot({ path: "../docs/screenshots/narrow-workbench.png" });
});

test("camera preference survives refresh while scene starts empty", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByText("Simulation connected", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Edit front camera" }).click();
  await page.getByLabel("Camera position X").fill("0.95");
  await page.getByRole("button", { name: "Apply camera" }).click();
  await expect(
    page.getByRole("dialog", { name: "Edit camera" }),
  ).not.toBeVisible();
  await page.reload();
  await expect(
    page.getByText("Simulation connected", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Edit front camera" }).click();
  await expect(page.getByLabel("Camera position X")).toHaveValue("0.95");
  await expect(
    page.getByText("Your tabletop is a blank canvas."),
  ).toBeVisible();
});
