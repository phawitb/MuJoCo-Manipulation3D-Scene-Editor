import { test, expect } from "@playwright/test";
let sid = "";
test.beforeEach(async ({ page, request }) => {
  const r = await request.post("/api/sessions");
  expect(r.ok()).toBeTruthy();
  sid = (await r.json()).sessionId;
  await page.goto("/?session=" + sid);
  await expect(page.getByTestId("asset-kalas_bowl")).toBeVisible();
});
test.afterEach(async ({ page, request }) => {
  await page.close();
  if (sid) await request.delete("/api/sessions/" + sid);
});
test("only IKEA utensils and cube are offered", async ({ page }) => {
  await expect(page.locator(".asset-card")).toHaveCount(5);
  await expect(page.getByTestId("asset-spoon")).toHaveCount(0);
  await expect(page.getByTestId("asset-cube")).toHaveCount(1);
});
test("pointer placement never starts native drag; Escape and outside release cancel", async ({
  page,
  request,
}) => {
  await page.evaluate(() => {
    document.addEventListener("dragstart", () => {
      document.documentElement.dataset.nativeDrag = "yes";
    });
  });
  await page.getByRole("button", { name: "Top view", exact: true }).click();
  const view = page.getByTestId("viewport-top");
  await expect
    .poll(async () => (await view.locator("canvas").boundingBox())?.width || 0)
    .toBeGreaterThan(600);
  const card = page.getByTestId("asset-kalas_bowl");
  const box = (await view.locator("canvas").boundingBox())!;
  const start = async () => {
    await card.scrollIntoViewIfNeeded();
    const b = (await card.boundingBox())!;
    await page.mouse.move(b.x + 30, b.y + 40);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, {
      steps: 12,
    });
  };
  await start();
  await expect(view).not.toHaveAttribute("data-preview-position", "");
  await expect(page.locator("html")).not.toHaveAttribute(
    "data-native-drag",
    "yes",
  );
  await expect(page.getByTestId("placement-preview")).toHaveCount(0);
  await page.keyboard.press("Escape");
  await page.mouse.up();
  await expect(view).toHaveAttribute("data-preview-position", "");
  await start();
  await page.mouse.move(30, 30);
  await page.mouse.up();
  expect(
    (await (await request.get("/api/sessions/" + sid)).json()).scene.objects,
  ).toHaveLength(0);
  await start();
  const reset = (await page
    .getByRole("button", { name: "Reset top camera", exact: true })
    .boundingBox())!;
  await page.mouse.move(reset.x + reset.width / 2, reset.y + reset.height / 2);
  await page.mouse.up();
  expect(
    (await (await request.get("/api/sessions/" + sid)).json()).scene.objects,
  ).toHaveLength(0);
  await start();
  await card.dispatchEvent("pointercancel", { pointerId: 1 });
  await page.mouse.up();
  await expect(view).toHaveAttribute("data-preview-position", "");
  await start();
  await expect
    .poll(async () => {
      const point = JSON.parse(
        (await view.getAttribute("data-preview-position")) || "null",
      );
      return point ? Math.hypot(point[0], point[1]) : Infinity;
    })
    .toBeLessThan(0.001);
  const position = JSON.parse(
    (await view.getAttribute("data-preview-position"))!,
  );
  await page.mouse.up();
  await expect(page.getByLabel("Object name")).toHaveValue("IKEA KALAS bowl");
  const objects = (await (await request.get("/api/sessions/" + sid)).json())
    .scene.objects;
  expect(objects).toHaveLength(1);
  objects[0].position.forEach((v: number, i: number) =>
    expect(v).toBeCloseTo(position[i], 6),
  );
  await expect(view).toHaveAttribute("data-preview-position", "");
});

test("dropping into another viewport activates that camera", async ({
  page,
}) => {
  const view = page.getByTestId("viewport-top");
  await expect(page.getByTestId("viewport-main")).toHaveClass(/active/);
  const card = page.getByTestId("asset-kalas_bowl");
  await card.scrollIntoViewIfNeeded();
  const source = (await card.boundingBox())!;
  const target = (await view.locator("canvas").boundingBox())!;
  await page.mouse.move(source.x + 30, source.y + 40);
  await page.mouse.down();
  await page.mouse.move(
    target.x + target.width / 2,
    target.y + target.height / 2,
    { steps: 12 },
  );
  await expect(view).not.toHaveAttribute("data-preview-position", "");
  await page.mouse.up();
  await expect(page.getByLabel("Object name")).toHaveValue("IKEA KALAS bowl");
  await expect(view).toHaveClass(/active/);
});
