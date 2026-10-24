import { test, expect, type Locator } from "@playwright/test";
import fs from "node:fs/promises";

// Read screenshot pixels after compositing rather than the WebGL drawing buffer,
// which browsers may clear between frames. A mounted canvas alone can be blank.
async function expectRenderedSolid(canvas: Locator) {
  await expect
    .poll(
      async () => {
        const screenshot = await canvas.screenshot();
        return canvas.evaluate(async (_element, encoded) => {
          const bytes = Uint8Array.from(atob(encoded), (c) => c.charCodeAt(0));
          const bitmap = await createImageBitmap(
            new Blob([bytes], { type: "image/png" }),
          );
          const image = document.createElement("canvas");
          image.width = bitmap.width;
          image.height = bitmap.height;
          const context = image.getContext("2d")!;
          context.drawImage(bitmap, 0, 0);
          bitmap.close();
          const pixels = context.getImageData(
            0,
            0,
            image.width,
            image.height,
          ).data;
          let solidPixels = 0;
          for (let i = 0; i < pixels.length; i += 4) {
            if (pixels[i] > 60 && pixels[i + 1] > 90 && pixels[i + 2] > 80)
              solidPixels++;
          }
          return solidPixels;
        }, screenshot.toString("base64"));
      },
      {
        message:
          "The solid must actually render; axes or an empty canvas are insufficient",
      },
    )
    .toBeGreaterThan(1000);
}

test("local image creates preview and GLB, then imports only into the explicitly selected Gym", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 1600, height: 1400 });
  const first = await (await request.post("/api/sessions")).json();
  const destination = await (await request.post("/api/sessions")).json();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  try {
    await page.goto(`/?session=${first.sessionId}`);
    await page.getByRole("tab", { name: "Blender", exact: true }).click();
    const module = page.locator(".blender-module");
    await expect(
      module.getByRole("heading", { name: "Blender", exact: true }),
    ).toBeVisible();
    await expect(module.getByLabel("Gym session")).toHaveValue("");
    const png = await page.evaluate(() => {
      const canvas = document.createElement("canvas");
      canvas.width = 80;
      canvas.height = 100;
      const ctx = canvas.getContext("2d")!;
      ctx.fillStyle = "white";
      ctx.fillRect(0, 0, 80, 100);
      ctx.fillStyle = "black";
      ctx.fillRect(10, 10, 60, 80);
      ctx.fillStyle = "white";
      ctx.fillRect(25, 30, 30, 40);
      return canvas.toDataURL("image/png").split(",")[1];
    });
    await module.getByLabel("Object image").setInputFiles({
      name: "hole-object.png",
      mimeType: "image/png",
      buffer: Buffer.from(png, "base64"),
    });
    await module.getByLabel("Width (mm)", { exact: true }).fill("120");
    await module.getByLabel("Height (mm)", { exact: true }).fill("160");
    await module.getByLabel("Depth (mm)", { exact: true }).fill("30");
    await module
      .getByRole("button", { name: "Create 3D object", exact: true })
      .click();
    await expect(
      module.getByText("Closed solid · Drag to orbit · Scroll to zoom"),
    ).toBeVisible();
    await expectRenderedSolid(module.locator("canvas"));
    await expect(
      module.getByAltText("Detected silhouette: white is the object"),
    ).toBeVisible();
    await expect(
      module.getByRole("button", { name: "Add to selected Gym" }),
    ).toBeDisabled();
    await module.evaluate((element) => element.scrollTo(0, 0));
    await page.screenshot({
      path: "/tmp/blender-extrusion.png",
      fullPage: true,
    });
    const downloading = page.waitForEvent("download");
    await module
      .getByRole("button", { name: "Download Blender-compatible GLB" })
      .click();
    const download = await downloading;
    expect(download.suggestedFilename()).toBe("hole-object.glb");
    const path = await download.path();
    expect((await fs.readFile(path!)).subarray(0, 4).toString()).toBe("glTF");
    await module.getByLabel("Gym session").selectOption(destination.sessionId);
    await module.getByRole("button", { name: "Add to selected Gym" }).click();
    await expect(
      module.getByRole("status").filter({ hasText: "Added" }),
    ).toContainText("Added");
    const after = await (
      await request.get(`/api/sessions/${destination.sessionId}`)
    ).json();
    expect(after.scene.objects).toHaveLength(1);
    expect(after.scene.objects[0].mesh.faces.length).toBeGreaterThan(12);
    expect(
      (await (await request.get(`/api/sessions/${first.sessionId}`)).json())
        .scene.objects,
    ).toHaveLength(0);
    await page.getByRole("tab", { name: "Gym", exact: true }).click();
    await page.getByRole("tab", { name: "Blender", exact: true }).click();
    await expect(
      module.getByText("Closed solid · Drag to orbit · Scroll to zoom"),
    ).toBeVisible();
    await expectRenderedSolid(module.locator("canvas"));
    await module.getByLabel("Method", { exact: true }).selectOption("revolve");
    await module
      .getByRole("button", { name: "Create 3D object", exact: true })
      .click();
    await expect(
      module.getByText("Closed solid · Drag to orbit · Scroll to zoom"),
    ).toBeVisible();
    await expect(module.getByText(/120 × 120 × 160 mm/)).toBeVisible();
    await expect(
      module.getByText(/Revolve makes a solid symmetric outer shape/),
    ).toBeVisible();
    await expectRenderedSolid(module.locator("canvas"));
    await module.evaluate((element) => element.scrollTo(0, 0));
    await page.screenshot({ path: "/tmp/blender-revolve.png", fullPage: true });
    expect(errors).toEqual([]);
  } finally {
    await page.close();
    await request.delete(`/api/sessions/${first.sessionId}`);
    await request.delete(`/api/sessions/${destination.sessionId}`);
  }
});

test("blank image gives actionable error and no generated download", async ({
  page,
  request,
}) => {
  const session = await (await request.post("/api/sessions")).json();
  try {
    await page.goto(`/?session=${session.sessionId}`);
    await page.getByRole("tab", { name: "Blender", exact: true }).click();
    const module = page.locator(".blender-module");
    const png = await page.evaluate(() => {
      const canvas = document.createElement("canvas");
      canvas.width = 40;
      canvas.height = 40;
      const ctx = canvas.getContext("2d")!;
      ctx.fillStyle = "white";
      ctx.fillRect(0, 0, 40, 40);
      return canvas.toDataURL("image/png").split(",")[1];
    });
    await module.getByLabel("Object image").setInputFiles({
      name: "blank.png",
      mimeType: "image/png",
      buffer: Buffer.from(png, "base64"),
    });
    await module
      .getByRole("button", { name: "Create 3D object", exact: true })
      .click();
    await expect(module.getByRole("alert")).toContainText(
      "No distinct foreground",
    );
    await expect(
      module.getByRole("button", { name: "Download Blender-compatible GLB" }),
    ).toHaveCount(0);
  } finally {
    await page.close();
    await request.delete(`/api/sessions/${session.sessionId}`);
  }
});
