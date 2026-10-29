import { test, expect } from "@playwright/test";
import { readFile, mkdir, rename } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

test("No random records the current editor scene without visual or position variation", async ({
  page,
  request,
}) => {
  test.setTimeout(120000);
  const origin = "http://127.0.0.1:8765";
  const initial = await (await request.post(origin + "/api/sessions")).json();
  const sid = initial.sessionId;
  let ownedJob: string | undefined;
  const root = fileURLToPath(new URL("../../recordings/", import.meta.url));
  try {
    const example = await (
      await request.post(`${origin}/api/sessions/${sid}/command`, {
        data: { type: "example", exampleId: "kalas-cup-front" },
      })
    ).json();
    const scene = example.scene;
    scene.appearance.robot_color = "#123456";
    scene.appearance.motor_color = "#789abc";
    scene.appearance.background = "#445566";
    scene.appearance.table.pattern = "stripes";
    scene.appearance.table.secondary = "#654321";
    scene.appearance.table.repeat = 7;
    scene.appearance.table.roughness = 0.37;
    scene.appearance.environment = "room";
    scene.table.color = "#abcdef";
    scene.objects[0].color = "#876543";
    const loaded = await request.post(`${origin}/api/sessions/${sid}/command`, {
      data: { type: "load", scene },
    });
    expect(loaded.ok()).toBeTruthy();
    await page.goto(`/?session=${sid}`);
    await page
      .getByRole("button", { name: "Collect data", exact: true })
      .click();
    await page
      .getByLabel("Dataset scene", { exact: true })
      .selectOption("kalas-cup-left");
    await page
      .getByLabel("Dataset name", { exact: true })
      .fill("ui-no-random-check");
    await page
      .getByRole("button", { name: "Randomization", exact: true })
      .click();
    const noRandom = page.getByRole("button", {
      name: "No random",
      exact: true,
    });
    await noRandom.click({ timeout: 5000 });
    await expect(noRandom).toHaveAttribute("aria-pressed", "true");
    const panel = page.getByTestId("collection-page");
    expect(
      await panel
        .getByRole("checkbox")
        .evaluateAll((nodes) =>
          nodes.every((n) => !(n as HTMLInputElement).checked),
        ),
    ).toBe(true);
    await page.getByLabel("Randomize robot color", { exact: true }).check();
    await expect(noRandom).toHaveAttribute("aria-pressed", "false");
    await noRandom.click({ timeout: 5000 });
    await page.screenshot({
      path: "../docs/screenshots/collection-no-random.png",
    });
    await page.getByRole("button", { name: "Capture", exact: true }).click();
    await expect(page.getByLabel("Dataset scene", { exact: true })).toHaveValue(
      "",
    );
    await expect(page.getByLabel("Dataset name", { exact: true })).toHaveValue(
      "ui-no-random-check",
    );
    await expect(
      page.getByLabel("Randomize object positions", { exact: true }),
    ).not.toBeChecked();
    for (const view of ["main", "top", "back", "wrist"])
      await page.getByLabel(`Capture ${view} view`, { exact: true }).uncheck();
    await page.getByLabel("Episodes", { exact: true }).fill("1");
    await page.getByLabel("Frame rate", { exact: true }).selectOption("10");
    await page
      .getByLabel("Image resolution", { exact: true })
      .selectOption("320x240");
    const before = await (
      await request.get(`${origin}/api/sessions/${sid}`)
    ).json();
    const started = page.waitForResponse(
      (r) =>
        r.url().endsWith(`/api/sessions/${sid}/collection`) &&
        r.request().method() === "POST",
    );
    await page
      .getByRole("button", { name: "Start collection", exact: true })
      .click();
    const response = await started;
    expect(response.ok()).toBeTruthy();
    const payload = response.request().postDataJSON();
    expect(payload.scene_id).toBeNull();
    for (const [key, value] of Object.entries(payload.variation)) {
      if (Array.isArray(value)) expect(value, key).toEqual([]);
    }
    for (const key of ["positions", "lighting", "finishes"])
      expect(payload.variation[key], key).toBe(false);
    ownedJob = (await response.json()).id;
    const card = page.getByTestId(`collection-job-${ownedJob}`);
    await expect(
      card.getByText("1 successful · 0 unsuccessful", { exact: true }),
    ).toBeVisible({ timeout: 90000 });
    await expect(
      card.getByText("LeRobot format verified", { exact: true }),
    ).toBeVisible();
    const recipe = JSON.parse(
      await readFile(
        path.join(
          root,
          ownedJob!,
          "dataset/meta/collection/episode_000000.json",
        ),
        "utf8",
      ),
    );
    expect(recipe.success).toBe(true);
    expect(recipe.scene).toEqual(before.scene);
    const after = await (
      await request.get(`${origin}/api/sessions/${sid}`)
    ).json();
    expect(after.scene).toEqual(before.scene);
    expect(after.time).toBe(before.time);
  } finally {
    if (ownedJob) {
      await request.post(`${origin}/api/collection/jobs/${ownedJob}/cancel`);
      await expect
        .poll(
          async () =>
            (
              await (
                await request.get(`${origin}/api/collection/jobs/${ownedJob}`)
              ).json()
            ).status,
          { timeout: 30000 },
        )
        .toMatch(/^(completed|failed|cancelled|interrupted)$/);
      const dir = path.join(root, ownedJob);
      const payload = JSON.parse(
        await readFile(path.join(dir, "config.json"), "utf8"),
      );
      if (
        payload.session_id !== sid ||
        payload.config.name !== "ui-no-random-check"
      )
        throw Error("Not this test's recording");
      await mkdir("/tmp/so101-no-random-fixtures", { recursive: true });
      await rename(dir, path.join("/tmp/so101-no-random-fixtures", ownedJob));
    }
    await request.delete(`${origin}/api/sessions/${sid}`);
  }
});
