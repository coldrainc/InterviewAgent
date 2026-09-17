const test = require("node:test");
const assert = require("node:assert/strict");

const {
  commandForTask,
  idempotencyKey,
  normalizeToday,
  replaceTask,
  verificationLabel
} = require("../miniprogram/utils/learning");

test("normalizeToday creates a stable server-authoritative task projection", () => {
  const result = normalizeToday({
    contract_version: "learning.today.v1",
    today: {
      tasks: [
        { id: "a", title: "复习", done: false, version: "2", verification: { status: "rejected" } },
        { id: "b", title: "面试", done: true, version: 3, verification: { status: "verified" } }
      ]
    }
  });

  assert.equal(result.today.total_tasks, 2);
  assert.equal(result.today.tasks_done, 1);
  assert.equal(result.today.tasks[0].version, 2);
  assert.equal(result.today.tasks[0].verificationLabel, "证据未通过");
  assert.deepEqual(result.risks, []);
  assert.deepEqual(result.next_best_action, {});
});

test("replaceTask updates only the matching task and recomputes progress", () => {
  const current = normalizeToday({
    today: { tasks: [{ id: "a", done: false }, { id: "b", done: false }] }
  });
  const next = replaceTask(current, { id: "a", title: "复习", done: true, status: "completed", version: 4 });

  assert.equal(next.today.tasks[0].status, "completed");
  assert.equal(next.today.tasks[1].id, "b");
  assert.equal(next.today.tasks_done, 1);
});

test("task commands and idempotency keys preserve the learning contract", () => {
  assert.equal(commandForTask({ primary_action: { command: "start" } }), "start");
  assert.equal(commandForTask({ done: false }), "complete");
  assert.equal(commandForTask({ done: true }), "reopen");
  assert.equal(verificationLabel({ status: "needs_review" }), "等待复核");
  assert.equal(idempotencyKey("task-1", "complete", 123, 0.5), "miniapp:task-1:complete:123:500000");
});
