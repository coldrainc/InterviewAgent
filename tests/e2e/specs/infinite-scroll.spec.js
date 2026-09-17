import { test, expect } from "../fixtures/app.fixture.js";
import { createTestAccount } from "../fixtures/accounts.js";

const totalQuestions = 45;

function questionAt(index) {
  return {
    id: `question-${index + 1}`,
    practice_category: "algorithm",
    subject: "数据结构",
    question_type: "subjective",
    prompt: `无限滚动测试题 ${String(index + 1).padStart(2, "0")}`,
    choices: [],
    difficulty: "medium",
    tags: ["E2E"]
  };
}

test("prefetches long-list pages near the bottom and stops after the last page", async ({ app, page }) => {
  const requestedOffsets = [];

  await page.route("**/review-site/practice-questions?*", async (route) => {
    const url = new URL(route.request().url());
    const limit = Number(url.searchParams.get("limit") || 20);
    const offset = Number(url.searchParams.get("offset") || 0);
    requestedOffsets.push(offset);
    const items = Array.from(
      { length: Math.max(0, Math.min(limit, totalQuestions - offset)) },
      (_, index) => questionAt(offset + index)
    );

    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        items,
        total: totalQuestions,
        limit,
        offset,
        has_more: offset + items.length < totalQuestions,
        next_offset: offset + items.length < totalQuestions ? offset + items.length : null
      })
    });
  });

  await app.open();
  await app.register(createTestAccount("infinite-scroll"));
  await app.openSection("刷题训练");

  const list = page.locator(".training-question-list");
  const items = list.locator(".training-question-item");
  await expect.poll(() => items.count()).toBe(40);
  expect(requestedOffsets).toEqual([0, 20]);

  const position = await list.evaluate((node) => {
    const maximum = node.scrollHeight - node.clientHeight;
    node.scrollTop = Math.max(0, maximum - 400);
    node.dispatchEvent(new Event("scroll"));
    return { maximum, current: node.scrollTop };
  });
  expect(position.current).toBeLessThan(position.maximum);

  await expect.poll(() => items.count()).toBe(totalQuestions);
  expect(requestedOffsets).toEqual([0, 20, 40]);

  await list.evaluate((node) => {
    node.scrollTop = node.scrollHeight;
    node.dispatchEvent(new Event("scroll"));
  });
  await page.waitForTimeout(300);
  expect(requestedOffsets).toEqual([0, 20, 40]);
  await expect(items).toHaveCount(totalQuestions);
});
