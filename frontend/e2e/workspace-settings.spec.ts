import { test, expect, chromium } from "@playwright/test";
import { mkdtemp, rm, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("applied camera setup survives a complete browser restart", async ({
  baseURL,
}) => {
  const profile = await mkdtemp(join(tmpdir(), "so101-camera-"));
  const options = {
    channel: process.env.PLAYWRIGHT_CHROMIUM ? undefined : "chrome",
    headless: true,
    viewport: { width: 1600, height: 1000 },
    args: ["--enable-webgl", "--use-gl=angle", "--use-angle=metal"],
  };
  let context = await chromium.launchPersistentContext(profile, options);
  try {
    let page = await context.newPage();
    await page.goto(baseURL!);
    await page
      .getByRole("button", { name: "Edit back camera", exact: true })
      .click();
    await page.getByLabel("Camera position Z").fill("1.81");
    await page
      .getByRole("button", { name: "Apply camera", exact: true })
      .click();
    await expect(page.getByRole("dialog")).not.toBeVisible();
    // An older open scene can refresh the session cache; it must not overwrite Apply.
    await page.evaluate(() => {
      const c = JSON.parse(localStorage.getItem("so101.cameras")!);
      c.back.position[2] = 1.65;
      localStorage.setItem("so101.cameras", JSON.stringify(c));
    });
    await context.close();
    context = await chromium.launchPersistentContext(profile, options);
    page = await context.newPage();
    await page.goto(baseURL!);
    await expect(
      page.getByText("Simulation connected", { exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Edit back camera", exact: true })
      .click();
    await expect(page.getByLabel("Camera position Z")).toHaveValue("1.81");
  } finally {
    await context.close();
    await rm(profile, { recursive: true, force: true });
  }
});

test("compact library filters objects and table color survives save/open", async ({
  page,
  request,
}) => {
  const sid = (await (await request.post("/api/sessions")).json()).sessionId;
  try {
    await page.goto("/?session=" + sid);
    await expect(
      page.getByRole("combobox", { name: "Asset category" }),
    ).toBeVisible();
    await page
      .getByRole("combobox", { name: "Asset category" })
      .selectOption("Spoons");
    await expect(page.locator(".asset-card")).toHaveCount(1);
    await page
      .getByRole("combobox", { name: "Asset category" })
      .selectOption("All assets");
    await expect(page.locator(".asset-card")).toHaveCount(5);
    const library = (await page.locator(".library").boundingBox())!;
    const first = (await page.getByTestId("asset-kalas_bowl").boundingBox())!;
    expect(first.y - library.y).toBeLessThan(210);
    await expect(page.getByText("MuJoCo Physics", { exact: true })).toHaveCount(
      0,
    );
    await page
      .getByRole("button", { name: "Table & environment", exact: true })
      .first()
      .click();
    await page.getByLabel("Tabletop color").fill("#336699");
    await expect
      .poll(
        async () =>
          (await (await request.get("/api/sessions/" + sid)).json()).scene.table
            .color,
      )
      .toBe("#336699");
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Save scene", exact: true }).click();
    const file = await download;
    const data = await readFile((await file.path())!, "utf8");
    expect(JSON.parse(data).scene.table.color).toBe("#336699");
    await page.getByLabel("Tabletop color").fill("#b8c2bf");
    await expect
      .poll(
        async () =>
          (await (await request.get("/api/sessions/" + sid)).json()).scene.table
            .color,
      )
      .toBe("#b8c2bf");
    await page.getByTestId("scene-file").setInputFiles({
      name: "colored-table.json",
      mimeType: "application/json",
      buffer: Buffer.from(data),
    });
    await expect(page.getByText("Scene loaded", { exact: true })).toBeVisible();
    await page
      .getByRole("button", { name: "Table & environment", exact: true })
      .first()
      .click();
    await expect(page.getByLabel("Tabletop color")).toHaveValue("#336699");
    await expect(page.locator(".toast")).not.toBeVisible();
    await page.screenshot({
      path: "../docs/screenshots/workspace-settings.png",
    });
  } finally {
    await page.close();
    await request.delete("/api/sessions/" + sid);
  }
});
