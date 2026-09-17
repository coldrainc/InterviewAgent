const test = require("node:test");
const assert = require("node:assert/strict");

const storage = new Map();
let pageDefinition;
let switchedTo = "";

global.wx = {
  getStorageSync(key) { return storage.get(key); },
  setStorageSync(key, value) { storage.set(key, value); },
  removeStorageSync(key) { storage.delete(key); },
  switchTab({ url }) { switchedTo = url; },
  request() { throw new Error("unexpected network request"); }
};
global.Page = (definition) => { pageDefinition = definition; };

const api = require("../miniprogram/utils/api");
const { config } = require("../miniprogram/utils/config");
const { normalizeToday, todayCacheKey } = require("../miniprogram/utils/learning");

require("../miniprogram/pages/today/today");

function createPage(data = {}) {
  const page = {
    ...pageDefinition,
    data: { ...pageDefinition.data, ...data },
    setData(patch, callback) {
      this.data = { ...this.data, ...patch };
      if (callback) callback();
    }
  };
  return page;
}

test.beforeEach(() => {
  storage.clear();
  config.apiToken = "token";
  config.refreshToken = "refresh";
  config.tenantId = "tenant";
  config.userId = "user";
  switchedTo = "";
});

test("task card opens its business workspace without changing status", () => {
  const dashboard = normalizeToday({
    today: { tasks: [{
      id: "task-1", title: "算法训练", task_type: "practice",
      link_payload: { category: "leetcode", plan_id: "plan-1", day_id: "day-1", task_id: "task-1" }
    }] }
  });
  const page = createPage({ dashboard });

  page.openTaskCard({ currentTarget: { dataset: { id: "task-1" } } });

  assert.equal(switchedTo, "/pages/practice/practice");
  assert.ok([...storage.values()].some((value) => value && value.category === "leetcode"));
});

test("refresh stores a server-authoritative Today snapshot and sync cursor", async () => {
  api.learningToday = async () => ({
    contract_version: "learning.today.v1",
    authority: "server",
    today: { tasks: [{ id: "task-1", title: "复习", version: 1, done: false }] },
    risks: []
  });
  api.pullLearningChanges = async () => ({ next_cursor: "opaque-cursor" });
  const page = createPage();

  await page.refresh();

  assert.equal(page.data.offline, false);
  assert.equal(page.data.dashboard.today.tasks[0].id, "task-1");
  assert.equal(storage.get(todayCacheKey()).dashboard.contract_version, "learning.today.v1");
  assert.ok([...storage.values()].includes("opaque-cursor"));
});

test("refresh keeps cached Today read-only when the network is unavailable", async () => {
  const dashboard = normalizeToday({ today: { tasks: [{ id: "cached", title: "缓存任务" }] } });
  storage.set(todayCacheKey(), { dashboard, savedAt: "2026-09-05T00:00:00Z" });
  api.learningToday = async () => { throw new Error("offline"); };
  const page = createPage({ dashboard });

  await page.refresh();

  assert.equal(page.data.offline, true);
  assert.match(page.data.error, /只读缓存/);
});

test("command conflict applies current_task from the server", async () => {
  const dashboard = normalizeToday({
    today: { tasks: [{ id: "task-1", title: "复习", version: 1, done: false, primary_action: { command: "complete" } }] }
  });
  api.executeLearningTask = async () => {
    const error = new Error("conflict");
    error.status = 409;
    error.details = { current_task: { id: "task-1", title: "复习", version: 2, done: true, status: "completed" } };
    throw error;
  };
  const page = createPage({ dashboard });

  await page.runTask({ currentTarget: { dataset: { id: "task-1" } } });

  assert.equal(page.data.dashboard.today.tasks[0].version, 2);
  assert.equal(page.data.dashboard.today.tasks[0].done, true);
  assert.match(page.data.error, /服务端最新状态/);
});
