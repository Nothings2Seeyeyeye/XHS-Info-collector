// Read-only visual inspection of the real library through a disposable app database.
import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
const output = process.env.XHS_SCREENSHOT_DIR;
if (!output) throw new Error("Set XHS_SCREENSHOT_DIR to an artifact directory");
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  reducedMotion: "reduce",
});
const page = await context.newPage();
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
await page.goto("http://127.0.0.1:8766");
await page.getByLabel("用户名", { exact: true }).fill("界面预览");
await page.getByLabel("密码", { exact: true }).fill("preview-only-password");
if (await page.getByLabel("确认密码", { exact: true }).count()) {
  await page
    .getByLabel("确认密码", { exact: true })
    .fill("preview-only-password");
  await page.getByRole("button", { name: "创建工作台", exact: true }).click();
} else
  await page.getByRole("button", { name: "进入素材库", exact: true }).click();
await page.waitForFunction(
  () => document.querySelectorAll(".note-card").length >= 38,
);
await page.waitForFunction(() =>
  [...document.querySelectorAll(".note-cover img")]
    .slice(0, 5)
    .every((img) => img.complete && img.naturalWidth > 0),
);
await page.screenshot({
  path: `${output}/library.png`,
  animations: "disabled",
});
const notes = await (
  await page.request.get("http://127.0.0.1:8766/api/notes?page_size=100")
).json();
const imageNote = notes.items.find((note) => note.kind === "图集");
await page
  .getByRole("button", { name: `查看笔记：${imageNote.title}`, exact: true })
  .click();
await page.waitForFunction(() => {
  const img = document.querySelector(".detail-image");
  return img && img.complete && img.naturalWidth > 0;
});
await page.screenshot({
  path: `${output}/note-detail.png`,
  animations: "disabled",
});
await page.keyboard.press("Escape");
await page.getByRole("button", { name: /^视频/ }).click();
await page.waitForFunction(
  () => document.querySelectorAll(".note-card").length === 8,
);
await page.locator(".cover-button").first().click();
const video = page.locator("video");
await video.waitFor();
await page.waitForFunction(
  () => {
    const video = document.querySelector("video");
    return video && Number.isFinite(video.duration) && video.duration > 0;
  },
  { timeout: 15000 },
);
const videoInfo = await video.evaluate(async (el) => {
  el.muted = true;
  await el.play();
  el.currentTime = Math.min(2, el.duration / 2);
  return { duration: el.duration, readyState: el.readyState };
});
await page.waitForFunction(
  () => document.querySelector("video").currentTime > 0,
);
await video.evaluate((el) => el.pause());
await page.screenshot({
  path: `${output}/video-detail.png`,
  animations: "disabled",
});
await page.keyboard.press("Escape");
await page.getByRole("button", { name: "设置", exact: true }).click();
await page.getByLabel("默认模型").waitFor();
await page.screenshot({
  path: `${output}/settings.png`,
  animations: "disabled",
});
await page.getByRole("button", { name: /^全部素材/ }).click();
await page
  .getByRole("button", { name: `查看笔记：${imageNote.title}`, exact: true })
  .click();
await page.setViewportSize({ width: 390, height: 844 });
await page.screenshot({
  path: `${output}/mobile-detail.png`,
  animations: "disabled",
});
console.log(
  JSON.stringify({
    notes: notes.total,
    video: videoInfo,
    pageErrors: errors,
    output,
  }),
);
await browser.close();
