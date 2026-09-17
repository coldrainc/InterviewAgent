import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const sourceUrl = new URL("../src/renderer/utils/productSafety.js", import.meta.url);
const source = await readFile(sourceUrl, "utf8");
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const { productErrorMessage, redactSensitiveText } = await import(moduleUrl);

const secretCases = [
  "Authorization: Bearer abcdefghijklmnopqrstuvwxyz012345",
  "access_token=abcdefghijklmnopqrstuvwxyz012345",
  "refresh_token: abcdefghijklmnopqrstuvwxyz012345",
  "api_key=sk-abcdefghijklmnopqrstuvwxyz012345",
  "https://example.com/callback?token=abcdefghijklmnopqrstuvwxyz012345"
];

for (const value of secretCases) {
  const result = redactSensitiveText(value);
  assert.doesNotMatch(result, /abcdefghijklmnopqrstuvwxyz/u);
}

assert.equal(
  productErrorMessage("ECONNREFUSED http://127.0.0.1:8000/api/health"),
  "暂时无法连接服务，请检查网络后重试。"
);
assert.equal(
  productErrorMessage("Traceback: ValidationError request_id=12345678"),
  "操作没有完成，请稍后重试。"
);
assert.equal(productErrorMessage("当前昵称已被使用"), "当前昵称已被使用");

console.log("productSafety: all checks passed");
