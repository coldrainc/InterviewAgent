const fs = require("fs");
const path = require("path");

const required = [
  "miniprogram/app.js",
  "miniprogram/app.json",
  "miniprogram/pages/chat/chat.js",
  "miniprogram/pages/chat/chat.wxml",
  "miniprogram/pages/setup/setup.js",
  "miniprogram/pages/setup/setup.wxml",
  "miniprogram/pages/resumes/resumes.js",
  "miniprogram/pages/resumes/resumes.wxml",
  "miniprogram/pages/history/history.js",
  "miniprogram/pages/history/history.wxml",
  "miniprogram/pages/profile/profile.js",
  "miniprogram/pages/profile/profile.wxml",
  "miniprogram/pages/privacy/privacy.js",
  "miniprogram/pages/privacy/privacy.wxml",
  "miniprogram/utils/api.js"
];

const missing = required.filter((file) => !fs.existsSync(path.join(__dirname, "..", file)));
if (missing.length) {
  console.error(`Missing miniapp files:\n${missing.join("\n")}`);
  process.exit(1);
}

console.log("Miniapp structure OK");
