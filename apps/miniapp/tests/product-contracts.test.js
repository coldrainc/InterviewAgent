const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const storage = new Map();
const requests = [];
global.wx = {
  getStorageSync(key) { return storage.get(key); },
  setStorageSync(key, value) { storage.set(key, value); },
  removeStorageSync(key) { storage.delete(key); },
  request(options) {
    requests.push(options);
    options.success({ statusCode: 200, data: responseFor(options.url) });
  }
};

const api = require("../miniprogram/utils/api");

test.beforeEach(() => {
  storage.clear();
  requests.length = 0;
  api.setAuthTokens({ access_token: "owner-token", refresh_token: "refresh", tenant_id: "tenant-a", user_id: "user-a" });
});

test("review and interviewer APIs preserve authenticated server contracts", async () => {
  await api.listReviewPlans();
  await api.generateReviewPlan({ target_role: "AI 工程师", total_days: 14 });
  await api.checkinReviewPlan("plan/1", { elapsed_minutes: 30, note: "完成" });
  await api.listInterviewKits();
  await api.createInterviewKit({ target_role: "AI 工程师" });

  assert.deepEqual(requests.map((item) => [item.method || "GET", new URL(item.url).pathname]), [
    ["GET", "/review-site/plans"],
    ["POST", "/review-site/planner/generate"],
    ["POST", "/review-site/plans/plan%2F1/checkin"],
    ["GET", "/interviewer-workspace/kits"],
    ["POST", "/interviewer-workspace/kits"]
  ]);
  assert.ok(requests.every((item) => item.header.Authorization === "Bearer owner-token"));
});

test("logout clears credentials and owner-scoped identity", () => {
  api.setAuthTokens({});
  assert.equal(storage.has("interview_agent_token"), false);
  assert.equal(storage.has("interview_agent_refresh_token"), false);
  assert.equal(storage.has("interview_agent_user_id"), false);
});

test("customer-facing pages do not expose development or infrastructure controls", () => {
  const root = path.join(__dirname, "..", "miniprogram", "pages");
  const source = walk(root).filter((file) => /\.(js|wxml)$/.test(file)).map((file) => fs.readFileSync(file, "utf8")).join("\n");
  ["开发登录", "devLogin", "access_token", "Embedding：", "对象存储：", "租户：", "用户："].forEach((term) => {
    assert.equal(source.includes(term), false, `must not expose ${term}`);
  });
});

function responseFor(url) {
  if (url.includes("/review-site/plans") && !url.includes("checkin")) return [];
  if (url.includes("/interviewer-workspace/kits")) return [];
  return {};
}

function walk(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const target = path.join(directory, entry.name);
    return entry.isDirectory() ? walk(target) : [target];
  });
}
