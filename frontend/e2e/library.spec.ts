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
