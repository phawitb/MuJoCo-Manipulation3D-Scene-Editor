import { test, expect } from "@playwright/test";

for (const id of ["kalas-rim-to-plate", "kalas-loaded-cup-to-plate"]) {
  test(`${id}: preview and physically carry cup onto plate`, async ({
    page,
  }) => {
    test.setTimeout(120000);
    await page.goto("/");
    await expect(
      page.getByText("Simulation connected", { exact: true }),
    ).toBeVisible();
    await page.getByLabel("Task example", { exact: true }).selectOption(id);
    await page.getByRole("button", { name: "Load task example" }).click();
    await expect(page.getByTestId("task-instruction")).toContainText(
      "KALAS cup",
    );
    await expect(page.getByTestId("task-instruction")).toContainText(
      "KALAS plate",
    );
    const sid = await page
      .getByTestId("session-id")
      .getAttribute("data-session-id");
    const state = async () =>
      (await page.request.get(`/api/sessions/${sid}`)).json();
    const before = await state();
    await page
      .getByRole("button", { name: "Calculate path", exact: true })
      .click();
    await expect(page.getByTestId("plan-status")).toContainText("Path ready", {
      timeout: 60000,
    });
    expect((await state()).objects).toEqual(before.objects);
    await expect(page.getByTestId("viewport-main")).toHaveAttribute(
      "data-path-visible",
      "true",
    );
    await page
      .getByRole("button", { name: "Run simulation", exact: true })
      .click();
    await expect(page.getByTestId("task-status")).toHaveText("Complete", {
      timeout: 60000,
    });
    const result = await state();
    expect(result.task.success).toBe(true);
    expect(result.task.graspAssist).toBe(false);
    expect(result.task.contents).toEqual(
      id.includes("loaded") ? ["spoon"] : [],
    );
    if (id.includes("loaded"))
      await page.screenshot({
        path: "../docs/screenshots/cup-with-spoon-on-plate.png",
      });
  });
}
