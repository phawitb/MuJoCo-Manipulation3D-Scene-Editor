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
  await request.post(`http://127.0.0.1:8765/api/sessions/${sid}/command`, {
    data: { type: "example" },
  });
  try {
    await page.goto(`/?session=${sid}`);
    await page
      .getByRole("button", { name: "Collect data", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Collect demonstrations" }),
    ).toBeVisible();
    await page
      .getByLabel("Dataset name", { exact: true })
      .fill("ui-collection-smoke");
    await page.getByLabel("Episodes", { exact: true }).fill("1");
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
      page.getByLabel("Randomize robot color", { exact: true }),
    ).toBeChecked();
    await expect(
      page.getByLabel("Randomize table color", { exact: true }),
    ).toBeChecked();
    await expect(
      page.getByLabel("Randomize motor color", { exact: true }),
    ).not.toBeChecked();
    await expect(
      page.getByRole("button", { name: "Robot Orange", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
    await expect(
      page.getByRole("button", { name: "Robot Yellow", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
    await expect(
      page.getByRole("button", { name: "Robot Blue", exact: true }),
    ).toHaveAttribute("aria-pressed", "false");
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
    expect(completed.saved_episodes).toBe(1);
    expect(completed.total_frames).toBe(10);
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
