import { test, expect } from "@playwright/test";

test("fixed views ignore gestures; Top only zooms with robot side at bottom", async ({
  page,
  request,
}) => {
  const sid = (await (await request.post("/api/sessions")).json()).sessionId;
  const cameras = async () =>
    (await (await request.get("/api/sessions/" + sid)).json()).scene.cameras;
  const gesture = async (kind: string) => {
    await expect
      .poll(
        async () =>
          (
            await page
              .getByTestId("viewport-" + kind)
              .locator("canvas")
              .boundingBox()
          )?.width || 0,
      )
      .toBeGreaterThan(600);
    const b = (await page
      .getByTestId("viewport-" + kind)
      .locator("canvas")
      .boundingBox())!;
    await page.mouse.move(b.x + b.width * 0.6, b.y + b.height * 0.55);
    await page.mouse.down({ button: "right" });
    await page.mouse.move(b.x + b.width * 0.67, b.y + b.height * 0.65, {
      steps: 12,
    });
    await page.mouse.up({ button: "right" });
    await page.mouse.down();
    await page.mouse.move(b.x + b.width * 0.58, b.y + b.height * 0.52, {
      steps: 12,
    });
    await page.mouse.up();
  };
  try {
    await page.goto("/?session=" + sid);
    for (const kind of ["front", "back"]) {
      await page
        .getByRole("button", {
          name: kind === "front" ? "Front" : "Back",
          exact: true,
        })
        .click();
      const before = (await cameras())[kind];
      await gesture(kind);
      await page.mouse.wheel(0, -150);
      await page.keyboard.press("f");
      await page.waitForTimeout(350);
      expect((await cameras())[kind]).toEqual(before);
    }
    await page.getByRole("button", { name: "Top view", exact: true }).click();
    const before = (await cameras()).top;
    await gesture("top");
    await page.keyboard.press("f");
    await page.waitForTimeout(300);
    expect((await cameras()).top).toEqual(before);
    await page.mouse.wheel(0, -100);
    await expect
      .poll(async () => (await cameras()).top.zoom)
      .toBeGreaterThan(before.zoom);
    const after = (await cameras()).top;
    after.position.forEach((n: number, i: number) =>
      expect(n).toBeCloseTo(before.position[i], 8),
    );
    after.target.forEach((n: number, i: number) =>
      expect(n).toBeCloseTo(before.target[i], 8),
    );
    const view = page.getByTestId("viewport-top");
    const b = (await view.locator("canvas").boundingBox())!;
    const card = page.getByTestId("asset-cube");
    await card.scrollIntoViewIfNeeded();
    const a = (await card.boundingBox())!;
    await page.mouse.move(a.x + 30, a.y + 40);
    await page.mouse.down();
    await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2 + 50, {
      steps: 15,
    });
    await expect(view).not.toHaveAttribute("data-preview-position", "");
    await page.mouse.up();
    await expect(page.getByLabel("Object name")).toBeVisible();
    const scene = (await (await request.get("/api/sessions/" + sid)).json())
      .scene;
    expect(scene.objects[0].position[0]).toBeLessThan(-0.05);
    expect(Math.abs(scene.objects[0].position[1])).toBeLessThan(0.01);
  } finally {
    await page.close();
    await request.delete("/api/sessions/" + sid);
  }
});
