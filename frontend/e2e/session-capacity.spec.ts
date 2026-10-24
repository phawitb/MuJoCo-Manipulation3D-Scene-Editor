import { test, expect } from "@playwright/test";

test("a full server recovers automatically after a slot is freed", async ({
  page,
  request,
}) => {
  const occupied: string[] = [];
  try {
    for (let i = 0; i < 16; i++) {
      const result = await request.post("/api/sessions");
      expect(result.ok()).toBeTruthy();
      occupied.push((await result.json()).sessionId);
    }
    await page.goto("/");
    await expect(
      page.getByText(
        "16 sessions are already open. Close an unused session first.",
        { exact: true },
      ),
    ).toBeVisible();
    await request.delete(`/api/sessions/${occupied.pop()}`);
    await expect(
      page.getByText("Simulation connected", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText(
        "16 sessions are already open. Close an unused session first.",
        { exact: true },
      ),
    ).not.toBeVisible();
    await expect(
      page.getByRole("button", { name: "Calculate path", exact: true }),
    ).toBeEnabled();
  } finally {
    await page.close();
    for (const id of occupied) await request.delete(`/api/sessions/${id}`);
  }
});
