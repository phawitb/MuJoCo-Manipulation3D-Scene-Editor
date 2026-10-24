import { test, expect } from "@playwright/test";

for (const example of ["kalas-bowl-left", "kalas-cup-to-plate"]) {
  test(`${example} displays measured physical grip and completes after release`, async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page.getByTestId("grip-physics")).toContainText(
      "Contact physics",
    );
    await page
      .getByLabel("Task example", { exact: true })
      .selectOption(example);
    await page.getByRole("button", { name: "Load task example" }).click();
    const sid = await page
      .getByTestId("session-id")
      .getAttribute("data-session-id");
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
      path: `../docs/screenshots/contact-grip-${example}.png`,
    });
    await expect(page.getByTestId("task-status")).toContainText("Complete", {
      timeout: 30000,
    });
    const done = await (await page.request.get(`/api/sessions/${sid}`)).json();
    expect(done.task.held).toBe(false);
    expect(done.task.success).toBe(true);
  });
}
