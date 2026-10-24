import { test, expect } from "@playwright/test";

let sessionId: string;
test.beforeEach(async ({ page, request }) => {
  const response = await request.post("/api/sessions");
  expect(response.ok()).toBeTruthy();
  sessionId = (await response.json()).sessionId;
  await page.goto(`/?session=${sessionId}`);
  await expect(page.getByTestId("asset-kalas_bowl")).toBeVisible();
});
test.afterEach(async ({ page, request }) => {
  await page.close();
  if (sessionId) await request.delete(`/api/sessions/${sessionId}`);
});

for (const viewport of [
  { width: 1512, height: 800 },
  { width: 1280, height: 720 },
]) {
  test(`asset cards retain their complete artwork and labels at ${viewport.width}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    const clipped = await page
      .locator(".asset-card")
      .evaluateAll((cards) =>
        cards
          .filter((card) => card.scrollHeight > card.clientHeight + 1)
          .map((card) => card.textContent),
      );
    expect(
      clipped,
      "Cards must scroll inside the library instead of shrinking their contents",
    ).toEqual([]);
    const last = page.getByTestId("asset-cube");
    await last.scrollIntoViewIfNeeded();
    await expect(last.getByRole("button")).toBeInViewport();
  });
}

test("native drag omits the card image and places the selected object", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Top view", exact: true }).click();
  // Observe the actual browser drag-image boundary, preserving its native behavior.
  await page.evaluate(() => {
    const original = DataTransfer.prototype.setDragImage;
    DataTransfer.prototype.setDragImage = function (image, x, y) {
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = 32;
      const context = canvas.getContext("2d")!;
      if (
        image instanceof HTMLCanvasElement ||
        image instanceof HTMLImageElement
      ) {
        context.drawImage(image, 0, 0, 32, 32);
        document.documentElement.dataset.dragImageVisible = String(
          context
            .getImageData(0, 0, 32, 32)
            .data.some((v, i) => i % 4 === 3 && v > 0),
        );
      } else document.documentElement.dataset.dragImageVisible = "true";
      original.call(this, image, x, y);
    };
  });
  const view = page.getByTestId("viewport-top");
  await expect
    .poll(async () => (await view.locator("canvas").boundingBox())?.width || 0)
    .toBeGreaterThan(600);
  const box = (await view.locator("canvas").boundingBox())!;
  await page.getByTestId("asset-kalas_bowl").dragTo(view.locator("canvas"), {
    targetPosition: { x: box.width / 2, y: box.height / 2 },
  });
  await expect(page.locator("html")).toHaveAttribute(
    "data-drag-image-visible",
    "false",
  );
  await expect(page.getByLabel("Object name")).toHaveValue("IKEA KALAS bowl");
  await expect(view.getByTestId("placement-preview")).not.toBeVisible();
});
