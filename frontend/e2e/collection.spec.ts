import { test, expect } from "@playwright/test";

test("collect constrained multi-camera data and download a verified LeRobot dataset", async ({
  page,
  request,
}) => {
  test.setTimeout(120000);
  const initial = await (
    await request.post("http://127.0.0.1:8765/api/sessions")
  ).json();
  const sid = initial.sessionId;
  try {
    await page.goto(`/?session=${sid}`);
    await page
      .getByRole("button", { name: "Collect data", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Collect demonstrations" }),
    ).toBeVisible();
    await expect(page.getByLabel("Dataset scene", { exact: true })).toHaveValue(
      "kalas-cup-front",
    );
    await page.screenshot({
      path: "../docs/screenshots/collection-scenes.png",
    });
    await page
      .getByLabel("Dataset scene", { exact: true })
      .selectOption("kalas-cup-left");
    await expect(page.getByLabel("Dataset name", { exact: true })).toHaveValue(
      "kalas-cup-left-demonstrations",
    );
    await page
      .getByLabel("Dataset scene", { exact: true })
      .selectOption("kalas-cup-front");
    await expect(
      page.getByLabel("Randomize object positions", { exact: true }),
    ).toBeChecked();
    await expect(
      page.getByLabel("Position radius (cm)", { exact: true }),
    ).toHaveValue("2");
    await page
      .getByLabel("Dataset name", { exact: true })
      .fill("ui-collection-smoke");
    await page.getByLabel("Episodes", { exact: true }).fill("2");
    await page.getByLabel("Frame rate", { exact: true }).selectOption("10");
    await page
      .getByLabel("Image resolution", { exact: true })
      .selectOption("320x240");
    await page.getByLabel("Episode time limit", { exact: true }).fill("1");
    await page.getByLabel("Include failed episodes").check();
    await page
      .getByRole("button", { name: "Randomization", exact: true })
      .click();
    await expect(
      page.getByRole("button", {
        name: "Select all robot colors",
        exact: true,
      }),
    ).toBeInViewport();
    await expect(
      page.getByLabel("Randomize robot color", { exact: true }),
    ).toBeChecked();
    await expect(
      page.getByLabel("Randomize table color", { exact: true }),
    ).toBeChecked();
    await expect(
      page.getByLabel("Randomize motor color", { exact: true }),
    ).toBeChecked();
    await expect(
      page.getByRole("button", { name: "Robot Orange", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
    await expect(
      page.getByRole("button", { name: "Robot Yellow", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
    await expect(
      page.getByRole("button", { name: "Robot Blue", exact: true }),
    ).toHaveAttribute("aria-pressed", "false");
    for (const name of [
      "table",
      "motor",
      "table legs",
      "floor",
      "wall",
      "background",
      "object",
    ]) {
      await expect(
        page.getByRole("button", {
          name: `Select all ${name} colors`,
          exact: true,
        }),
      ).toHaveAttribute("aria-pressed", "true");
    }
    await page.screenshot({
      path: "../docs/screenshots/collection-all-palettes.png",
    });
    await page
      .getByRole("button", { name: "Select all robot colors", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: "Robot Blue", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: "Table Blue", exact: true }).click();
    await expect(
      page.getByRole("button", {
        name: "Select all table colors",
        exact: true,
      }),
    ).toHaveAttribute("aria-pressed", "false");
    await page
      .getByRole("button", { name: "Select all table colors", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: "Table Blue", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
    await expect(
      page.getByRole("button", {
        name: "Select all robot patterns",
        exact: true,
      }),
    ).toHaveAttribute("aria-pressed", "true");
    await expect(
      page.getByRole("button", {
        name: "Select all environment layouts",
        exact: true,
      }),
    ).toHaveAttribute("aria-pressed", "true");
    const before = await (
      await request.get(`http://127.0.0.1:8765/api/sessions/${sid}`)
    ).json();
    const started = page.waitForResponse(
      (response) =>
        response.url().endsWith(`/api/sessions/${sid}/collection`) &&
        response.request().method() === "POST",
    );
    await page
      .getByRole("button", { name: "Start collection", exact: true })
      .click();
    const jobResponse = await started;
    expect(jobResponse.ok()).toBeTruthy();
    const job = await jobResponse.json();
    const card = page.getByTestId(`collection-job-${job.id}`);
    await expect(
      card.getByText("Verified LeRobot dataset", { exact: true }),
    ).toBeVisible({ timeout: 90000 });
    const completed = await (
      await request.get(`http://127.0.0.1:8765/api/collection/jobs/${job.id}`)
    ).json();
    expect(completed.saved_episodes).toBe(2);
    expect(completed.scene_id).toBe("kalas-cup-front");
    await page
      .getByLabel("Filter datasets by scene", { exact: true })
      .selectOption("01 · Spoon into cup");
    await expect(card).toBeVisible();
    expect(completed.total_frames).toBe(20);
    const download = page.waitForEvent("download");
    await card
      .getByRole("link", { name: "Download dataset ZIP", exact: true })
      .click();
    expect((await download).suggestedFilename()).toContain("lerobot.zip");
    const after = await (
      await request.get(`http://127.0.0.1:8765/api/sessions/${sid}`)
    ).json();
    expect(after.scene).toEqual(before.scene);
    expect(after.time).toEqual(before.time);
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(
      page.getByRole("button", { name: "Close data collection" }),
    ).toBeInViewport();
  } finally {
    await request.delete(`http://127.0.0.1:8765/api/sessions/${sid}`);
  }
});
