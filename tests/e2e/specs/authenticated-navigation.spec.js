import { test, expect } from "../fixtures/app.fixture.js";
import { createTestAccount } from "../fixtures/accounts.js";

test("registers a user and reaches the main learning journeys", async ({ app, page }) => {
  const account = createTestAccount("navigation");
  await app.open();
  await app.register(account);

  await expect(app.sidebar).toContainText(account.displayName);
  await app.openSection("刷题训练");
  await app.openSection("复习站");
  await app.openSection("计划生成器");
  await app.openSection("模拟面试");

  await app.expectNoSensitiveText();
  await app.expectNoHorizontalOverflow();
});

test("collapses the sidebar and keeps theme colors coherent", async ({ app, page }) => {
  await app.open();
  await app.register(createTestAccount("appearance"));

  const lightBackground = await app.sidebar.evaluate((node) => getComputedStyle(node).backgroundColor);
  expect(lightBackground).not.toBe("rgb(21, 25, 34)");

  await app.toggleTheme();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  const darkBackground = await app.sidebar.evaluate((node) => getComputedStyle(node).backgroundColor);
  expect(darkBackground).not.toBe(lightBackground);

  await page.getByRole("button", { name: "收起菜单" }).click();
  await expect(app.appShell).toHaveClass(/sidebar-collapsed/);
  await page.getByRole("button", { name: "展开菜单" }).click();
  await expect(app.appShell).not.toHaveClass(/sidebar-collapsed/);
});

test("review site has no infinite flashing animation", async ({ app, page }) => {
  await app.open();
  await app.register(createTestAccount("review"));
  await app.openSection("复习站");
  await expect(page.locator(".review-site .skeleton")).toHaveCount(0);

  const infiniteAnimations = await page.evaluate(() =>
    document.getAnimations()
      .filter((animation) => animation.effect?.getTiming().iterations === Infinity)
      .map((animation) => ({
        name: animation.animationName,
        target: animation.effect?.target?.className || animation.effect?.target?.tagName || "unknown"
      }))
  );
  expect(infiniteAnimations).toEqual([]);
});

test("today task card opens content while its action only changes status", async ({ app, page }) => {
  await page.route("**/learning/today", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        contract_version: "learning.today.v1",
        authority: "server",
        today: {
          plan_id: "plan-e2e",
          plan_title: "E2E 计划",
          total_tasks: 1,
          tasks_done: 0,
          tasks: [{
            id: "task-click",
            task_key: "task-click",
            title: "算法训练",
            task_type: "practice",
            status: "todo",
            version: 0,
            done: false,
            tags: ["算法"],
            verification: { status: "not_run", mode: "none" },
            primary_action: { command: "start", label: "开始刷题" },
            link_payload: {
              plan_id: "plan-e2e",
              day_id: "day-e2e",
              task_id: "task-click",
              category: "leetcode"
            }
          }]
        },
        next_best_action: { kind: "task", task_id: "task-click", title: "算法训练", action: { label: "开始刷题" } },
        risks: [],
        streak: {},
        study_minutes: {},
        interviews: {},
        practice: {},
        plan: {},
        weak_points: []
      })
    });
  });
  await page.route("**/learning/tasks/task-click/commands", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        task: { id: "task-click", status: "in_progress", version: 1, done: false },
        receipt: { accepted: true },
        idempotent_replay: false
      })
    });
  });

  await app.open();
  await app.register(createTestAccount("task-card"));
  await expect(page.getByRole("button", { name: "打开任务：算法训练" })).toBeVisible();

  await page.locator(".home-task-go").click();
  await expect(page.getByRole("heading", { name: /早上好|中午好|下午好|晚上好/ })).toBeVisible();

  await page.getByRole("button", { name: "打开任务：算法训练" }).click();
  await expect(page.locator(".training-page").getByRole("heading", { name: "刷题训练" })).toBeVisible();
});
