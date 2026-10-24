import { test, expect } from "@playwright/test";

test("back camera edits, persists, renders without a reset button; legacy scenes still open", async ({
  page,
  request,
}) => {
  const sid = (await (await request.post("/api/sessions")).json()).sessionId;
  try {
    await page.goto("/?session=" + sid);
    await expect(page.getByTestId("viewport-back")).toBeVisible();
    await page.getByRole("button", { name: "Back", exact: true }).click();
    await page
      .getByRole("button", { name: "Edit back camera", exact: true })
      .click();
    await expect(page.getByLabel("Camera position X")).toHaveValue("-0.3");
    await expect(page.getByLabel("Camera position Z")).toHaveValue("1.65");
    await page.getByLabel("Camera position Z").fill("1.7");
    await page
      .getByRole("button", { name: "Apply camera", exact: true })
      .click();
    await expect(page.getByRole("dialog")).not.toBeVisible();
    await page.reload();
    await page.getByRole("button", { name: "Back", exact: true }).click();
    await page
      .getByRole("button", { name: "Edit back camera", exact: true })
      .click();
    await expect(page.getByLabel("Camera position Z")).toHaveValue("1.7");
    await page.getByRole("button", { name: "Close camera editor" }).click();
    const image = await request.get(
      "/api/sessions/" + sid + "/image?view=back",
    );
    expect(image.ok()).toBeTruthy();
    expect((await image.body()).subarray(0, 8)).toEqual(
      Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    );
    await expect(
      page.getByRole("button", { name: "Reset back camera" }),
    ).toHaveCount(0);
    await page.setViewportSize({ width: 800, height: 900 });
    await expect(
      page.getByRole("button", { name: "Back", exact: true }),
    ).toBeInViewport();
    await expect(
      page.getByRole("button", { name: "Edit back camera" }),
    ).toBeInViewport();
    const state = await (await request.get("/api/sessions/" + sid)).json();
    const cameras = structuredClone(state.scene.cameras);
    delete cameras.back;
    delete state.scene.cameras.back;
    const file = JSON.stringify({ version: 1, scene: state.scene, cameras });
    await page.getByTestId("scene-file").setInputFiles({
      name: "legacy.json",
      mimeType: "application/json",
      buffer: Buffer.from(file),
    });
    await expect(page.getByText("Scene loaded", { exact: true })).toBeVisible();
    await page
      .getByRole("button", { name: "Edit back camera", exact: true })
      .click();
    await expect(page.getByLabel("Camera position Z")).toHaveValue("1.65");
  } finally {
    await page.close();
    await request.delete("/api/sessions/" + sid);
  }
});
