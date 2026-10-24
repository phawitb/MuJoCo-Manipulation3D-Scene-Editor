import { test, expect } from "@playwright/test";

for (const { example, reset } of [
  { example: "kalas-bowl-left", reset: false },
  { example: "kalas-cup-to-plate", reset: false },
  { example: "kalas-cup-to-plate", reset: true },
]) {
  test(`${example}${reset ? " from saved downward wrist" : ""} displays measured physical grip and completes after release`, async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page.getByTestId("grip-physics")).toContainText(
      "Contact physics",
    );
    await page
      .getByLabel("Task example", { exact: true })
      .selectOption(example);
    if (reset) {
      const session = await page
        .getByTestId("session-id")
        .getAttribute("data-session-id");
      const update = await page.request.post(
        `/api/sessions/${session}/command`,
        {
          data: {
            type: "robot",
            patch: { reset_joints: [0, -1.5, 1.5, 0.985937, 0, 0] },
          },
        },
      );
      expect(update.ok()).toBeTruthy();
    }
    await page.getByRole("button", { name: "Load task example" }).click();
    const sid = await page
      .getByTestId("session-id")
      .getAttribute("data-session-id");
    if (reset) {
      const start = await (
        await page.request.get(`/api/sessions/${sid}`)
      ).json();
      expect(start.scene.robot.joints).toEqual([0, -1.5, 1.5, 0.985937, 0, 0]);
      // Reproduce the saved old arrangement: report the actual initial overlap.
      start.scene.objects.find(
        (o: { id: string }) => o.id === "spoon",
      ).position = [-0.09978705, 0.10469775, 0.82612671];
      start.scene.objects.find(
        (o: { id: string }) => o.id === "source_cup",
      ).position = [-0.12, 0.09, 0.79044761];
      const load = await page.request.post(`/api/sessions/${sid}/command`, {
        data: { type: "load", scene: start.scene },
      });
      expect(load.ok()).toBeTruthy();
      await page
        .getByRole("button", { name: "Calculate path", exact: true })
        .click();
      await expect(page.locator(".plan-feedback")).toContainText(
        "Starting pose overlaps",
      );
      await expect(page.locator(".plan-feedback")).toContainText(
        "wrist camera",
      );
      await expect(page.locator(".plan-feedback")).toContainText(
        "Source · KALAS cup",
      );
      await page.getByRole("button", { name: "Load task example" }).click();
    }
    await page
      .getByRole("button", { name: "Calculate path", exact: true })
      .click();
    await expect(page.getByTestId("plan-status")).toContainText("Path ready", {
      timeout: 45000,
    });
    await page
      .getByRole("button", { name: "Run simulation", exact: true })
      .click();
    await expect(page.getByTestId("grip-physics")).toContainText(
      "Grip confirmed",
      { timeout: 15000 },
    );
    const state = await (await page.request.get(`/api/sessions/${sid}`)).json();
    expect(state.task.graspAssist).toBe(false);
    expect(state.task.grip.secure).toBe(true);
    expect(state.task.grip.leftForce).toBeGreaterThan(0.02);
    expect(state.task.grip.rightForce).toBeGreaterThan(0.02);
    await page.screenshot({
      path: `../docs/screenshots/contact-grip-${example}${reset ? "-custom-reset" : ""}.png`,
    });
    await expect(page.getByTestId("task-status")).toContainText("Complete", {
      timeout: 30000,
    });
    const done = await (await page.request.get(`/api/sessions/${sid}`)).json();
    expect(done.task.held).toBe(false);
    expect(done.task.success).toBe(true);
  });
}
