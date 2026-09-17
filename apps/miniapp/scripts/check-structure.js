const fs = require("fs");
const path = require("path");

const required = [
  "miniprogram/app.js",
  "miniprogram/app.json",
  "miniprogram/pages/today/today.js",
  "miniprogram/pages/today/today.wxml",
  "miniprogram/pages/today/today.wxss",
  "miniprogram/pages/chat/chat.js",
  "miniprogram/pages/chat/chat.wxml",
  "miniprogram/pages/setup/setup.js",
  "miniprogram/pages/setup/setup.wxml",
  "miniprogram/pages/setup/setup.wxss",
  "miniprogram/pages/practice/practice.js",
  "miniprogram/pages/practice/practice.wxml",
  "miniprogram/pages/practice/practice.wxss",
  "miniprogram/pages/review/review.js",
  "miniprogram/pages/review/review.wxml",
  "miniprogram/pages/review/review.wxss",
  "miniprogram/pages/resumes/resumes.js",
  "miniprogram/pages/resumes/resumes.wxml",
  "miniprogram/pages/history/history.js",
  "miniprogram/pages/history/history.wxml",
  "miniprogram/pages/profile/profile.js",
  "miniprogram/pages/profile/profile.wxml",
  "miniprogram/pages/privacy/privacy.js",
  "miniprogram/pages/privacy/privacy.wxml",
  "miniprogram/utils/api.js",
  "miniprogram/utils/auth.js",
  "miniprogram/utils/learning.js",
  "miniprogram/utils/interviewSetup.js",
  "miniprogram/assets/app-icon.png"
];

const missing = required.filter((file) => !fs.existsSync(path.join(__dirname, "..", file)));
if (missing.length) {
  console.error(`Missing miniapp files:\n${missing.join("\n")}`);
  process.exit(1);
}

console.log("Miniapp structure OK");

const appConfig = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "miniprogram/app.json"), "utf8"));
if (appConfig.pages[0] !== "pages/today/today") {
  console.error("Today must be the default miniapp page");
  process.exit(1);
}
if (!appConfig.tabBar.list.some((item) => item.pagePath === "pages/today/today")) {
  console.error("Today must be reachable from the miniapp tab bar");
  process.exit(1);
}
const expectedTabs = ["pages/today/today", "pages/chat/chat", "pages/practice/practice", "pages/review/review", "pages/profile/profile"];
if (JSON.stringify(appConfig.tabBar.list.map((item) => item.pagePath)) !== JSON.stringify(expectedTabs)) {
  console.error("Miniapp primary navigation must be Today, Interview, Practice, Review, Mine");
  process.exit(1);
}

console.log("Miniapp navigation contract OK");
