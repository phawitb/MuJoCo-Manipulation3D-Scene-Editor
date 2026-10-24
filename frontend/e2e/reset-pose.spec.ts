import { test, expect } from "@playwright/test";

test("saved reset pose survives reset, example loading and a new browser session", async ({
  page,
  request,
  context,
}) => {
  let sid = "";
  page.on("websocket", (socket) =>
    socket.on("framereceived", (event) => {
      const packet = JSON.parse(String(event.payload));
      if (packet.sessionId) sid = packet.sessionId;
    }),
  );
  await page.goto("/");
  await expect(
    page.getByText("Simulation connected", { exact: true }),
  ).toBeVisible();

  const read = async () =>
    (await (await request.get(`/api/sessions/${sid}`)).json()).scene;
  try {
    for (const kind of ["front", "back"])
      await expect(
        page.getByRole("button", { name: `Reset ${kind} camera`, exact: true }),
      ).toHaveCount(0);
    await page
      .getByRole("button", { name: "SO-101 arm FIXED", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: "Save current pose as reset" }),
    ).toBeVisible();
    const slider = page.getByRole("slider", {
      name: "shoulder_pan slider",
      exact: true,
    });
    await slider.focus();
    await slider.press("ArrowRight");
    await expect
      .poll(async () => (await read()).robot.joints[0])
      .toBeGreaterThan(0);
    const saved = (await read()).robot.joints;
    await page
      .getByRole("button", { name: "Save current pose as reset" })
      .click();
    await expect(
      page.getByText("Reset position saved", { exact: true }),
    ).toBeVisible();
    await slider.focus();
    await slider.press("ArrowRight");
    await expect
      .poll(async () => (await read()).robot.joints[0])
      .toBeGreaterThan(saved[0]);
    await page
      .getByRole("button", { name: "Reset scene", exact: true })
      .click();
    await expect.poll(async () => (await read()).robot.joints).toEqual(saved);
    await page
      .getByRole("button", { name: "Load task example", exact: true })
      .click();
    await expect
      .poll(async () => (await read()).objects.length)
      .toBeGreaterThan(0);
    expect((await read()).robot.joints).toEqual(saved);
    const storageState = await context.storageState();
    // Reopening an existing session must not apply a different browser default.
    await page.evaluate(() =>
      localStorage.setItem(
        "so101.robot-reset-position",
        JSON.stringify([0.4, 0, 0, 0, 0, 0]),
      ),
    );
    await page.goto("/?session=" + sid);
    await expect(
      page.getByText("Simulation connected", { exact: true }),
    ).toBeVisible();
    expect((await read()).robot.reset_joints).toEqual(saved);
    const reopened = await context.browser()!.newContext({ storageState });
    const next = await reopened.newPage();
    let nextId: string | null = null;
    try {
      next.on("websocket", (socket) =>
        socket.on("framereceived", (event) => {
          const packet = JSON.parse(String(event.payload));
          if (packet.sessionId) nextId = packet.sessionId;
        }),
      );
      await next.goto(new URL("/", page.url()).href);
      await expect(
        next.getByText("Simulation connected", { exact: true }),
      ).toBeVisible();

      expect(
        (await (await request.get(`/api/sessions/${nextId}`)).json()).scene
          .robot.joints,
      ).toEqual(saved);
      await next
        .getByRole("button", { name: "SO-101 arm FIXED", exact: true })
        .click();
      await next
        .getByRole("button", { name: "Use folded default", exact: true })
        .click();
      await expect
        .poll(
          async () =>
            (await (await request.get(`/api/sessions/${nextId}`)).json()).scene
              .robot.joints[0],
        )
        .toBe(0);
      await expect(next.locator(".joint-control").first()).toContainText(
        "0.0°",
      );
      await expect(next.locator(".toast")).not.toBeVisible();
      await next.screenshot({
        path: "../docs/screenshots/robot-reset-position.png",
      });
    } finally {
      await reopened.close();
      if (nextId) await request.delete(`/api/sessions/${nextId}`);
    }
  } finally {
    await page.close();
    await request.delete(`/api/sessions/${sid}`);
  }
});
