import { test, expect } from "@playwright/test";

test("empty Inspector lists objects, highlights selection and keyboard nudges only outside forms", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Load task example" }).click();
  await expect(page.getByTestId("inspector-object-spoon")).toBeVisible();
  await page.getByTestId("inspector-object-spoon").click();
  await expect(page.getByTestId("viewport-main")).toHaveAttribute(
    "data-highlight",
    "spoon",
  );
  const sid = await page
    .getByTestId("session-id")
    .getAttribute("data-session-id");
  const read = async () =>
    (
      await (await page.request.get(`/api/sessions/${sid}`)).json()
    ).scene.objects.find((o: { id: string }) => o.id === "spoon").position;
  const before = await read();
  await page.keyboard.press("ArrowRight");
  await expect
    .poll(async () => (await read())[0])
    .toBeCloseTo(before[0] + 0.01, 4);
  await page.keyboard.press("Shift+ArrowUp");
  await expect
    .poll(async () => (await read())[1])
    .toBeCloseTo(before[1] + 0.001, 4);
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowRight");
  await expect
    .poll(async () => (await read())[0])
    .toBeCloseTo(before[0] + 0.04, 4);
  await page.getByLabel("Position X").focus();
  const after = await read();
  await page.keyboard.press("ArrowLeft");
  expect(await read()).toEqual(after);
});

test("calculating previews rainbow path without moving, then edits invalidate it", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Load task example" }).click();
  const sid = await page
    .getByTestId("session-id")
    .getAttribute("data-session-id");
  const before = await (await page.request.get(`/api/sessions/${sid}`)).json();
  await page
    .getByRole("button", { name: "Calculate path", exact: true })
    .click();
  await expect(page.getByTestId("plan-status")).toContainText("Path ready", {
    timeout: 60000,
  });
  await expect(page.getByTestId("viewport-main")).toHaveAttribute(
    "data-path-visible",
    "true",
  );
  const after = await (await page.request.get(`/api/sessions/${sid}`)).json();
  expect(after.objects).toEqual(before.objects);
  expect(after.joints).toEqual(before.joints);
  expect(after.plan.points.length).toBeGreaterThan(30);
  await page.screenshot({ path: "../docs/screenshots/path-preview.png" });
  await page.getByTestId("inspector-object-spoon").click();
  await page.keyboard.press("ArrowRight");
  await expect(
    page.getByRole("button", { name: "Calculate path", exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("viewport-main")).toHaveAttribute(
    "data-path-visible",
    "false",
  );
});

test("asset drag shows a ghost before drop and removes it on cancellation", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Top view", exact: true }).click();
  const transfer = await page.evaluateHandle(() => new DataTransfer());
  await page
    .getByTestId("asset-kalas_bowl")
    .dispatchEvent("dragstart", { dataTransfer: transfer });
  const view = page.getByTestId("viewport-top");
  await expect
    .poll(async () => (await view.locator("canvas").boundingBox())?.width || 0)
    .toBeGreaterThan(600);
  const box = await view.locator("canvas").boundingBox();
  await expect
    .poll(async () => {
      // Native dragging sends repeated dragover events as the viewport renders.
      await view.dispatchEvent("dragover", {
        dataTransfer: transfer,
        clientX: box!.x + box!.width / 2,
        clientY: box!.y + box!.height / 2,
      });
      return view.getByTestId("placement-preview").isVisible();
    })
    .toBe(true);
  await expect(view.getByTestId("placement-preview")).toContainText(
    "IKEA KALAS bowl",
  );
  await page.screenshot({ path: "../docs/screenshots/placement-preview.png" });
  await page
    .getByTestId("asset-kalas_bowl")
    .dispatchEvent("dragend", { dataTransfer: transfer });
  await expect(view.getByTestId("placement-preview")).not.toBeVisible();
  expect(
    await page.locator('[data-testid^="object-kalas_bowl_"]').count(),
  ).toBe(0);
});

test("task buttons pulse their current object and every example is selectable", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Load task example" }).click();
  await page.getByRole("button", { name: "Choose pick object" }).click();
  await expect(page.getByTestId("viewport-main")).toHaveAttribute(
    "data-highlight",
    "spoon",
  );
  await page.getByRole("button", { name: "Choose place object" }).click();
  await expect(page.getByTestId("viewport-main")).toHaveAttribute(
    "data-highlight",
    "cup",
  );
  await page.getByRole("button", { name: "Cancel task selection" }).click();
  await expect(
    page.getByLabel("Task example", { exact: true }).locator("option"),
  ).toHaveCount(10);
  await page
    .getByLabel("Task example", { exact: true })
    .selectOption("kalas-bowl-clutter");
  await page.getByRole("button", { name: "Load task example" }).click();
  await expect(page.getByTestId("inspector-object-other_bowl")).toBeVisible();
  await expect(page.getByTestId("task-instruction")).toContainText(
    "KALAS bowl",
  );
});

test("ghost coordinates exactly match final drop position", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Top view", exact: true }).click();
  const view = page.getByTestId("viewport-top");
  await expect
    .poll(async () => (await view.locator("canvas").boundingBox())?.width || 0)
    .toBeGreaterThan(600);
  const box = (await view.locator("canvas").boundingBox())!;
  const transfer = await page.evaluateHandle(() => new DataTransfer());
  await page
    .getByTestId("asset-kalas_bowl")
    .dispatchEvent("dragstart", { dataTransfer: transfer });
  const event = {
    dataTransfer: transfer,
    clientX: box.x + box.width / 2 + 40,
    clientY: box.y + box.height / 2 - 20,
  };
  await view.dispatchEvent("dragover", event);
  await expect(view.getByTestId("placement-preview")).toBeVisible();
  const position = JSON.parse(
    (await view.getAttribute("data-preview-position"))!,
  );
  await view.dispatchEvent("drop", event);
  await expect(page.getByLabel("Object name")).toHaveValue("IKEA KALAS bowl");
  const sid = await page
    .getByTestId("session-id")
    .getAttribute("data-session-id");
  const state = await (await page.request.get(`/api/sessions/${sid}`)).json();
  state.scene.objects[0].position.forEach((v: number, i: number) =>
    expect(v).toBeCloseTo(position[i], 6),
  );
  await expect(view.getByTestId("placement-preview")).not.toBeVisible();
  // A blank part of the tabletop clears selection back to the current-object list.
  await view
    .locator("canvas")
    .click({ position: { x: box.width / 2 + 90, y: box.height / 2 + 60 } });
  await expect(
    page.getByTestId(`inspector-object-${state.scene.objects[0].id}`),
  ).toBeVisible();
});
