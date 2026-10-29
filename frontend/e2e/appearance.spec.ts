import { test, expect } from "@playwright/test";

test("appearance presets, seeded variation and portable recipes", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Appearance Studio", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Appearance Studio" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Color lab", exact: true }).click();
  await expect(page.getByLabel("Table pattern", { exact: true })).toHaveValue(
    "checker",
  );
  await page.getByLabel("Table pattern", { exact: true }).selectOption("wood");
  await page
    .getByRole("button", { name: "Apply appearance", exact: true })
    .click();
  await expect(
    page.getByText("Appearance applied", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Randomize", exact: true }).click();
  await page.getByLabel("Random seed", { exact: true }).fill("42");
  await page.getByRole("button", { name: "Apply seed", exact: true }).click();
  await expect(
    page.getByText("Applied seed 42", { exact: true }),
  ).toBeVisible();
  const download = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Export recipes", exact: true })
    .click();
  expect((await download).suggestedFilename()).toContain("recipes");
  await page.getByRole("button", { name: "Surfaces", exact: true }).click();
  await page.getByRole("button", { name: "Color lab", exact: true }).click();
  await expect(
    page.getByText("Color lab applied", { exact: true }),
  ).toBeVisible();
  await page.screenshot({ path: "test-results/appearance-studio.png" });
  await page.getByRole("button", { name: "Close Appearance Studio" }).click();
  await expect(
    page.getByRole("heading", { name: "Appearance Studio" }),
  ).not.toBeVisible();
});

test("appearance draft survives camera snapshots and fits a narrow screen", async ({
  page,
  request,
}) => {
  const initial = await (
    await request.post("http://127.0.0.1:8765/api/sessions")
  ).json();
  const sid = initial.sessionId;
  try {
    let latestSequence = -1;
    page.on("websocket", (socket) =>
      socket.on("framereceived", (event) => {
        const packet = JSON.parse(String(event.payload));
        if (packet.type === "snapshot") latestSequence = packet.sequence;
      }),
    );
    await page.goto(`/?session=${sid}`);
    await page
      .getByRole("button", { name: "Appearance Studio", exact: true })
      .click();
    await page
      .getByLabel("Table pattern", { exact: true })
      .selectOption("dots");
    const response = await (
      await request.post(`http://127.0.0.1:8765/api/sessions/${sid}/command`, {
        data: {
          type: "camera",
          camera: "main",
          value: {
            position: [1.1, -1.3, 1.5],
            target: [0, 0, 0.75],
            zoom: 1,
            fov: 42,
          },
        },
      })
    ).json();
    await expect
      .poll(() => latestSequence)
      .toBeGreaterThanOrEqual(response.sequence);
    await expect(page.getByLabel("Table pattern", { exact: true })).toHaveValue(
      "dots",
    );
    await expect(
      page.getByRole("button", { name: "Apply appearance", exact: true }),
    ).toBeEnabled();
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(
      page.getByRole("button", { name: "Apply appearance", exact: true }),
    ).toBeInViewport();
    await expect(
      page.getByRole("button", { name: "Close Appearance Studio" }),
    ).toBeInViewport();
    await page
      .getByRole("button", { name: "Apply appearance", exact: true })
      .press("Space");
    await expect(
      page.getByText("Appearance applied", { exact: true }),
    ).toBeVisible();
  } finally {
    await request.delete(`http://127.0.0.1:8765/api/sessions/${sid}`);
  }
});

test("reapplying the saved preset replaces unapplied drafts", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Appearance Studio", exact: true })
    .click();
  await page.getByLabel("Table pattern", { exact: true }).selectOption("dots");
  await page
    .getByRole("button", { name: "Original studio", exact: true })
    .click();
  await expect(
    page.getByText("Original studio applied", { exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Table pattern", { exact: true })).toHaveValue(
    "solid",
  );
  await expect(
    page.getByRole("button", { name: "Apply appearance", exact: true }),
  ).toBeDisabled();
});
