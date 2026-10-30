import { test, expect } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

test("folder and ZIP preview, insert, source colors, duplicate and scene reopen", async ({
  page,
  request,
}) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (e) => browserErrors.push(e.message));
  const origin = "http://127.0.0.1:8765";
  const sid = (await (await request.post(origin + "/api/sessions")).json())
    .sessionId;
  const folder = fileURLToPath(
    new URL("./fixtures/mujoco-puck/", import.meta.url),
  );
  const temp = await mkdtemp(path.join(tmpdir(), "package-import-"));
  try {
    await page.goto("/?session=" + sid);
    await page
      .getByRole("button", { name: "Import object", exact: true })
      .click();
    await page
      .getByRole("button", { name: "MuJoCo package", exact: true })
      .click({ timeout: 5000 });
    await page.getByTestId("package-folder").setInputFiles(folder);
    await page
      .getByRole("button", { name: "Review package", exact: true })
      .click();
    await expect(page.getByTestId("package-summary")).toContainText(
      "Package puck",
    );
    await expect(page.getByTestId("package-summary")).toContainText("45");
    await page
      .getByRole("button", { name: "Import and place", exact: true })
      .click();
    await expect(
      page.getByRole("dialog", { name: "Import object" }),
    ).toHaveCount(0);
    const read = async () =>
      (await (await request.get(`${origin}/api/sessions/${sid}`)).json()).scene;
    let scene = await read();
    expect(scene.objects).toHaveLength(1);
    expect(scene.objects[0].asset).toBe("mujoco");
    expect(scene.objects[0].package_color_override).toBe(false);
    await page.getByLabel("Surface color", { exact: true }).fill("#ff0000");
    await expect
      .poll(async () => (await read()).objects[0].package_color_override)
      .toBe(true);
    await page
      .getByRole("button", { name: "Restore package colors", exact: true })
      .click();
    await expect
      .poll(async () => (await read()).objects[0].package_color_override)
      .toBe(false);
    await page
      .getByRole("button", { name: "Import object", exact: true })
      .click();
    await page
      .getByRole("button", { name: "MuJoCo package", exact: true })
      .click();
    const zip = path.join(temp, "puck.zip");
    execFileSync("python3", [
      "-c",
      'import pathlib,zipfile,sys\np=pathlib.Path(sys.argv[1])\nwith zipfile.ZipFile(sys.argv[2],"w") as z:\n for f in p.rglob("*"):\n  if f.is_file(): z.write(f,"nested/"+str(f.relative_to(p)))',
      folder,
      zip,
    ]);
    await page.getByTestId("package-zip").setInputFiles(zip);
    await page
      .getByRole("button", { name: "Review package", exact: true })
      .click();
    await expect(page.getByTestId("package-summary")).toContainText(
      "Package puck",
    );
    await page
      .getByRole("button", { name: "Import and place", exact: true })
      .click();
    await expect.poll(async () => (await read()).objects.length).toBe(2);
    scene = await read();
    expect(browserErrors).toEqual([]);
    await expect(page.getByTestId("viewport-main")).toBeVisible();
    expect(scene.objects[0].package).toEqual(scene.objects[1].package);
    expect(scene.objects[0].id).not.toBe(scene.objects[1].id);
    const loaded = await request.post(`${origin}/api/sessions/${sid}/command`, {
      data: { type: "load", scene },
    });
    expect(loaded.ok()).toBeTruthy();
    expect((await read()).objects).toEqual(scene.objects);
    await page.screenshot({
      path: "../docs/screenshots/package-import-puck.png",
    });
  } finally {
    await request.delete(`${origin}/api/sessions/${sid}`);
    await rm(temp, { recursive: true, force: true });
  }
});
