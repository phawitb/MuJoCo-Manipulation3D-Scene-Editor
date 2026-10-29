import { test, expect } from "@playwright/test";

test("a full server recovers automatically after a slot is freed", async ({
  page,
  request,
}) => {
  const occupied: string[] = [];
  try {
    for (let i = 0; i < 16; i++) {
      const result = await request.post("/api/sessions");
      // A live editor may already own a slot. Fill the remaining capacity
      // without deleting or assuming ownership of the user's sessions.
      if (result.status() === 422) {
        expect((await result.json()).detail).toBe(
          "16 sessions are already open. Close an unused session first.",
        );
        break;
      }
      expect(result.ok()).toBeTruthy();
      occupied.push((await result.json()).sessionId);
    }
    expect(occupied.length).toBeGreaterThan(0);
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
