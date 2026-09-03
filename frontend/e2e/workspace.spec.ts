import { test, expect } from "@playwright/test";

test("initialize, browse, organize, restore, export and collect an existing note", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByLabel("用户名", { exact: true }).fill("体验测试");
  await page.getByLabel("密码", { exact: true }).fill("local-e2e-password");
  await page.getByLabel("确认密码", { exact: true }).fill("local-e2e-password");
  await page.getByRole("button", { name: "创建工作台", exact: true }).click();
  await expect(page.locator(".note-card")).toHaveCount(2);
  await page.getByLabel("搜索素材").fill("独特露营清单");
  await expect(page.locator(".note-card")).toHaveCount(1);
  await page.getByRole("button", { name: "清空搜索" }).click();
  await expect(page.locator(".note-card")).toHaveCount(2);
  await page.getByRole("button", { name: "查看笔记：露营收纳灵感" }).click();
  const detail = page.getByRole("dialog");
  await expect(
    detail.getByRole("heading", { name: "露营收纳灵感", exact: true }).last(),
  ).toBeVisible();
  await expect(detail.locator(".detail-image")).toBeVisible();
  await detail.getByRole("button", { name: "下一张图片" }).click();
  await expect(detail.locator(".image-counter")).toHaveText("2 / 2");
  await detail.getByRole("tab", { name: "图片文字" }).click();
  await expect(detail.locator(".ocr-text")).toContainText("独特露营清单");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "新建文件夹", exact: true }).click();
  await page.getByLabel("文件夹名称").fill("拍摄参考");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(
    page.locator(".folder-label").filter({ hasText: "拍摄参考" }),
  ).toBeVisible();
  // Exercise the pointer interaction in addition to the equivalent menus.
  await page.getByRole("button", { name: "新建文件夹", exact: true }).click();
  await page.getByLabel("文件夹名称").fill("灵感子集");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  const child = page.locator(".folder-row").filter({ hasText: "灵感子集" });
  await child.hover();
  const folderHandle = page.getByRole("button", {
    name: "拖动文件夹 灵感子集",
    exact: true,
  });
  const parent = page.locator(".folder-row").filter({ hasText: "拍摄参考" });
  let from = await folderHandle.boundingBox(),
    to = await parent.boundingBox();
  if (!from || !to) throw new Error("folder drag target missing");
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
  await page.mouse.down();
  await page.mouse.move(from.x + 14, from.y + 14);
  await page.mouse.move(to.x + 50, to.y + to.height / 2, { steps: 15 });
  await page.mouse.up();
  await expect
    .poll(async () => {
      const result = await (await page.request.get("/api/overview")).json();
      return result.folders.find((f: { name: string }) => f.name === "灵感子集")
        .parent_id;
    })
    .not.toBeNull();
  const noteHandle = page.getByRole("button", {
    name: "拖动笔记 露营收纳灵感",
    exact: true,
  });
  await noteHandle.hover();
  from = await noteHandle.boundingBox();
  to = await child.boundingBox();
  if (!from || !to) throw new Error("note drag target missing");
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
  await page.mouse.down();
  await page.mouse.move(from.x + 14, from.y + 14);
  await page.mouse.move(to.x + 60, to.y + to.height / 2, { steps: 15 });
  await page.mouse.up();
  await expect
    .poll(async () => {
      const result = await (
        await page.request.get("/api/notes/aaaaaaaaaaaaaaaaaaaaaaaa")
      ).json();
      return result.folder_ids.length;
    })
    .toBe(1);
  // Cover keyboard selection after dragging. dnd-kit suppresses click events for
  // 50 ms after pointer-up to prevent accidentally opening the dropped card.
  const selectionCheckbox = page.getByLabel("选择 露营收纳灵感", { exact: true });
  await selectionCheckbox.focus();
  await selectionCheckbox.press("Space", { delay: 80 });
  await expect(selectionCheckbox).toBeChecked();
  await page.getByRole("button", { name: "放入文件夹", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "确定", exact: true })
    .click();
  await page.locator(".folder-label").filter({ hasText: "拍摄参考" }).click();
  await expect(page.locator(".note-card")).toHaveCount(1);
  await page.getByLabel("选择 露营收纳灵感", { exact: true }).check();
  await page
    .locator(".selection-bar")
    .getByRole("button", { name: "标签", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByLabel("标签", { exact: true })
    .fill("下次拍");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "确定", exact: true })
    .click();
  await expect(page.locator(".card-tags")).toContainText("下次拍");
  await page
    .locator(".selection-bar")
    .getByRole("button", { name: "移入回收站" })
    .click();
  await expect(page.locator(".note-card")).toHaveCount(0);
  await page.getByRole("button", { name: /^回收站/ }).click();
  await expect(page.locator(".note-card")).toHaveCount(1);
  await page.getByLabel("选择 露营收纳灵感", { exact: true }).check();
  await page
    .locator(".selection-bar")
    .getByRole("button", { name: "恢复", exact: true })
    .click();
  await expect(page.locator(".note-card")).toHaveCount(0);
  await page.locator(".folder-label").filter({ hasText: "拍摄参考" }).click();
  await expect(page.locator(".note-card")).toHaveCount(1);
  await page.getByLabel("选择 露营收纳灵感", { exact: true }).check();
  await page
    .locator(".selection-bar")
    .getByRole("button", { name: "导出", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByText("文字与结构化数据", { exact: true })
    .click();
  const download = page.waitForEvent("download");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "导出", exact: true })
    .click();
  expect((await download).suggestedFilename()).toMatch(/\.zip$/);
  await page.getByRole("button", { name: "取消选择", exact: true }).click();
  await page.getByRole("button", { name: "链接采集", exact: true }).click();
  await page
    .getByLabel("链接或分享内容")
    .fill(
      "https://www.xiaohongshu.com/explore/aaaaaaaaaaaaaaaaaaaaaaaa?xsec_token=test",
    );
  await page.getByRole("button", { name: "创建采集任务", exact: true }).click();
  await expect(page.locator(".job-result-summary")).toContainText("已完成", {
    timeout: 25000,
  });
  await expect(page.locator(".note-card")).toHaveCount(1);
  await page.getByRole("button", { name: "查看笔记：露营收纳灵感" }).click();
  await expect(page.locator(".detail-content")).toContainText("下次拍");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "设置", exact: true }).click();
  await expect(page.getByLabel("默认模型")).toHaveValue("PaddleOCR-VL-1.6");
  await page.getByLabel("默认模型").fill("custom-ocr-model");
  await page.getByRole("button", { name: "保存设置", exact: true }).click();
  await page.reload();
  await page.getByRole("button", { name: "设置", exact: true }).click();
  await expect(page.getByLabel("默认模型")).toHaveValue("custom-ocr-model");
  await page.getByRole("button", { name: /^全部素材/ }).click();
  await page.screenshot({
    path: "test-results/workspace-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true);
  await page.getByRole("button", { name: "查看笔记：露营收纳灵感" }).click();
  await expect(page.locator(".detail-content")).toBeVisible();
  await page.screenshot({
    path: "test-results/workspace-mobile-detail.png",
    fullPage: true,
    animations: "disabled",
  });
  expect(errors).toEqual([]);
});
