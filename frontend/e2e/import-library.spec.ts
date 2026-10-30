import { test, expect } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { readFile } from "node:fs/promises";

test.skip(
  !process.env.SO101_LIBRARY_E2E,
  "Use npm run test:library for isolated persistent storage",
);

// Run against an isolated server with SO101_IMPORT_LIBRARY set to a temporary
// directory. These tests intentionally persist library entries across reloads.
test("placed imports remain searchable and reusable with plus and drag after reload", async ({
  page,
  request,
}) => {
  const sid = (await (await request.post("/api/sessions")).json()).sessionId;
  const folder = fileURLToPath(
    new URL("./fixtures/mujoco-puck/", import.meta.url),
  );
  const read = async () =>
    (await (await request.get(`/api/sessions/${sid}`)).json()).scene;
  try {
    await page.goto("/?session=" + sid);
    const before = (await (await request.get("/api/imported-assets")).json())
      .length;
    await page
      .getByRole("button", { name: "Import object", exact: true })
      .click();
    await page
      .getByRole("button", { name: "MuJoCo package", exact: true })
      .click();
    await page.getByTestId("package-folder").setInputFiles(folder);
    await page
      .getByRole("button", { name: "Review package", exact: true })
      .click();
    await expect(page.getByTestId("package-summary")).toContainText(
      "Package puck",
    );
    expect(
      (await (await request.get("/api/imported-assets")).json()).length,
    ).toBe(before);
    await page
      .getByRole("button", { name: "Import and place", exact: true })
      .click();
    await expect(
      page.getByRole("dialog", { name: "Import object" }),
    ).toHaveCount(0);
    await page.reload();
    await page.getByLabel("Asset category").selectOption("Imported");
    await page.getByLabel("Search assets").fill("package puck");
    const add = page.getByRole("button", {
      name: "Add Package puck",
      exact: true,
    });
    await expect(add).toBeVisible();
    await add.click();
    await expect.poll(async () => (await read()).objects.length).toBe(2);
    const card = page.locator(".asset-card").filter({ has: add });
    const cardBounds = (await card.boundingBox())!;
    const viewport = (await page.getByTestId("viewport-main").boundingBox())!;
    await page.mouse.move(
      cardBounds.x + cardBounds.width / 2,
      cardBounds.y + 35,
    );
    await page.mouse.down();
    await page.mouse.move(
      viewport.x + viewport.width * 0.55,
      viewport.y + viewport.height * 0.6,
      { steps: 12 },
    );
    await page.mouse.up();
    await expect.poll(async () => (await read()).objects.length).toBe(3);
    const objects = (await read()).objects;
    expect(new Set(objects.map((o: { id: string }) => o.id)).size).toBe(3);
    expect(objects[1].package).toEqual(objects[0].package);
    expect(objects[2].package).toEqual(objects[0].package);
    expect(objects[2].scale).toBe(objects[0].scale);
    expect(
      (await (await request.get("/api/imported-assets")).json()).filter(
        (a: { name: string }) => a.name === "Package puck",
      ),
    ).toHaveLength(1);
  } finally {
    await request.delete(`/api/sessions/${sid}`);
  }
});

test("existing scene imports migrate with a visible retry on storage failure", async ({
  page,
  request,
}) => {
  const sid = (await (await request.post("/api/sessions")).json()).sessionId;
  try {
    const files = await Promise.all(
      ["object.xml", "assets.xml", "puck.obj"].map(async (path) => ({
        path,
        data: (
          await readFile(
            new URL(`./fixtures/mujoco-puck/${path}`, import.meta.url),
          )
        ).toString("base64"),
      })),
    );
    const template = await (
      await request.post("/api/import/package", { data: { files } })
    ).json();
    template.id = "legacy_import";
    template.position = [0.05, 0, 0.79];
    expect(
      (
        await request.post(`/api/sessions/${sid}/command`, {
          data: { type: "object_add", object: template },
        })
      ).ok(),
    ).toBeTruthy();
    await page.route("**/api/imported-assets?*", (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          detail:
            "Object is placed but could not be saved to the imported library: Disk unavailable",
        }),
      }),
    );
    await page.goto("/?session=" + sid);
    await expect(page.getByRole("alert")).toContainText("Disk unavailable");
    await page.unroute("**/api/imported-assets?*");
    await page
      .getByRole("button", { name: "Retry library save", exact: true })
      .click();
    await expect(page.getByRole("alert")).toHaveCount(0);
    const scene = (await (await request.get(`/api/sessions/${sid}`)).json())
      .scene;
    expect(scene.objects).toHaveLength(1);
    expect(scene.objects[0].id).toBe("legacy_import");
    expect(scene.objects[0].package).toEqual(template.package);
  } finally {
    await request.delete(`/api/sessions/${sid}`);
  }
});
