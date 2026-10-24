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
  // HTTP state can lead the WebSocket acknowledgement that re-enables inputs.
  await expect(page.getByLabel("Position X")).toBeEnabled();
  await page.getByLabel("Position X").focus();
  await expect(page.getByLabel("Position X")).toBeFocused();
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
  ).toHaveCount(13);
  await page
    .getByLabel("Task example", { exact: true })
    .selectOption("kalas-bowl-clutter");
  await page.getByRole("button", { name: "Load task example" }).click();
  await expect(page.getByTestId("inspector-object-other_bowl")).toBeVisible();
  await expect(page.getByTestId("task-instruction")).toContainText(
    "KALAS bowl",
  );
});
