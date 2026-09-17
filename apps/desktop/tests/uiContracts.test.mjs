import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const app = await readFile(new URL("../src/renderer/App.jsx", import.meta.url), "utf8");
const foundation = await readFile(new URL("../src/renderer/styles/foundation.css", import.meta.url), "utf8");
const reviewData = await readFile(new URL("../src/renderer/features/review-site/useReviewSiteData.js", import.meta.url), "utf8");
const reviewPage = await readFile(new URL("../src/renderer/components/study/ReviewSitePage.jsx", import.meta.url), "utf8");
const reviewToday = await readFile(new URL("../src/renderer/features/review-site/ReviewTodayComponents.jsx", import.meta.url), "utf8");
const reviewTaskDrawer = await readFile(new URL("../src/renderer/features/review-site/ReviewTaskDetailDrawer.jsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/renderer/styles.css", import.meta.url), "utf8");
const viteConfig = await readFile(new URL("../vite.config.js", import.meta.url), "utf8");
const sidebar = await readFile(new URL("../src/renderer/components/sidebar/Sidebar.jsx", import.meta.url), "utf8");
const adminPage = await readFile(new URL("../src/renderer/components/admin/AdminConsole.jsx", import.meta.url), "utf8");
const adminModels = await readFile(new URL("../src/renderer/components/admin/AdminModelsPanel.jsx", import.meta.url), "utf8");
const adminUsers = await readFile(new URL("../src/renderer/components/admin/AdminUsersPanel.jsx", import.meta.url), "utf8");
const adminOverview = await readFile(new URL("../src/renderer/components/admin/AdminOverview.jsx", import.meta.url), "utf8");
const adminStyles = await readFile(new URL("../src/renderer/styles/admin.css", import.meta.url), "utf8");
const adminApi = await readFile(new URL("../src/renderer/api/adminClient.js", import.meta.url), "utf8");
const apiClient = await readFile(new URL("../src/renderer/apiClient.js", import.meta.url), "utf8");
const mainProcess = await readFile(new URL("../src/main.js", import.meta.url), "utf8");
const todayTasks = await readFile(new URL("../src/renderer/features/today/TodayTaskList.jsx", import.meta.url), "utf8");
const taskTarget = await readFile(new URL("../src/renderer/features/today/taskTarget.js", import.meta.url), "utf8");
const infiniteScroll = await readFile(new URL("../src/renderer/hooks/useInfiniteScroll.js", import.meta.url), "utf8");
const trainingPage = await readFile(new URL("../src/renderer/components/training/TrainingPage.jsx", import.meta.url), "utf8");

assert.match(app, /if \(!account\) \{[\s\S]*?<AuthGate/u, "未登录状态必须走独立入口");
assert.match(app, /const \[authReady, setAuthReady\]/u, "登录态恢复前不能闪出产品工作台");

assert.match(foundation, /--sidebar-bg:\s*#ffffff/u, "浅色主题必须提供浅色侧栏变量");
assert.match(foundation, /\[data-theme="dark"\][\s\S]*--sidebar-bg:\s*#151922/u, "深色主题必须覆盖侧栏变量");
assert.match(foundation, /\.sidebar\s*\{[\s\S]*background:\s*var\(--sidebar-bg\)/u, "侧栏背景必须跟随主题变量");

const bootstrapBody = reviewData.match(/async function bootstrap\(\) \{([\s\S]*?)\n  \}/u)?.[1] || "";
assert.doesNotMatch(bootstrapBody, /runImport/u, "进入复习站时不能自动导入示例计划");
assert.doesNotMatch(reviewPage, /导入示例数据|handleRunImport|injectMockDemo/u, "普通复习站不能暴露管理员测试数据入口");
assert.doesNotMatch(reviewPage, /className="v3-btn primary cta-pulse"/u, "计划空状态不能持续闪动");
assert.doesNotMatch(styles, /v3-cta-pulse/u, "复习站不应保留无限 CTA 脉冲动画");
assert.match(reviewData, /planRequestRef/u, "计划详情请求必须避免旧响应覆盖新状态");
assert.match(reviewPage, /function toggleDay\(day, nextOpen\)/u, "每日打卡折叠状态必须使用 details 的目标状态");
assert.match(reviewPage, /currentlyOpen === shouldOpen\) return cur/u, "受控 details 状态一致时不得再次反转触发闪动");
assert.match(reviewToday, /role="button"[\s\S]*查看任务详情/u, "每日打卡任务整项必须可以进入详情");
assert.match(reviewToday, /event\.target !== event\.currentTarget/u, "任务卡键盘事件不能劫持内部控件");
assert.match(reviewToday, /event\.stopPropagation\(\)/u, "任务卡内的完成、评分和笔记操作不能误开详情");
assert.match(reviewTaskDrawer, /任务详情[\s\S]*验收标准[\s\S]*学习记录/u, "任务详情必须展示执行与验收信息");
assert.match(reviewTaskDrawer, /parsed\.protocol === "http:" \|\| parsed\.protocol === "https:"/u, "任务资料链接只允许安全 Web 协议");
assert.match(reviewPage, /onNavigate\?\.\("practice"/u, "刷题任务必须能从详情进入题库");
assert.match(reviewPage, /onStartInterview\?\./u, "模拟任务必须能从详情开始面试");
assert.match(viteConfig, /"\/api"[\s\S]*127\.0\.0\.1:8020/u, "本地开发服务器必须代理 API 请求");
assert.match(sidebar, /isAdmin[\s\S]*管理后台/u, "管理后台入口必须只对管理员展示");
assert.match(adminPage, /account\?\.role !== "admin"/u, "管理页面自身必须校验管理员角色");
assert.doesNotMatch(`${adminPage}\n${adminModels}\n${adminUsers}\n${adminOverview}`, /access_token|refresh_token|api_key|Authorization/u, "管理页面不得展示密钥或令牌字段");
assert.match(adminModels, /credential_status/u, "模型管理只能展示服务端凭据状态");
assert.match(adminModels, /useState\("enabled"\)/u, "模型管理默认应聚焦已启用模型");
assert.match(adminUsers, /admin-drawer/u, "用户管理应使用不打断上下文的侧滑抽屉");
assert.match(adminUsers, /不能停用当前登录的管理员账户/u, "用户管理必须提示当前管理员自保护规则");
assert.match(adminOverview, /运营待办/u, "管理概览必须提供可执行的运营待办");
assert.match(adminStyles, /\[data-theme="dark"\] \.admin-console/u, "管理后台必须完整适配深色主题");
assert.match(adminApi, /\/admin\/users/u, "管理后台必须使用受保护的服务端接口");
for (const header of ["X-Client-Platform", "X-Client-Version", "X-Client-Request-Id", "X-Request-ID"]) {
  assert.match(apiClient, new RegExp(header, "u"), `Web 请求缺少 ${header}`);
  assert.match(mainProcess, new RegExp(header, "u"), `桌面主进程请求缺少 ${header}`);
}
assert.match(apiClient, /electronBridge\(\) \? "desktop" : "web"/u, "Web 与桌面端必须使用不同平台标识");
assert.match(todayTasks, /role="button"[\s\S]*onClick=\{\(\) => onOpen\?\.\(task\)\}/u, "任务卡片必须可点击打开业务内容");
assert.match(todayTasks, /event\.stopPropagation\(\); onToggle\(task\)/u, "完成按钮不能触发卡片导航");
assert.match(todayTasks, /event\.stopPropagation\(\); onStart\(task\)/u, "状态按钮不能触发卡片导航");
for (const target of ["chat", "practice", "review-site"]) {
  assert.match(taskTarget, new RegExp(`screen: "${target}"`, "u"), `缺少 ${target} 任务目标映射`);
}
assert.match(
  apiClient,
  /fetch\(`\$\{apiBaseUrl\(\)\}\/auth\/refresh`[\s\S]*?headers:\s*buildHeaders/u,
  "刷新登录状态也必须携带统一客户端来源头"
);
assert.match(infiniteScroll, /rootMargin = "800px 0px"/u, "长列表必须在到达底部前预取下一页");
assert.match(infiniteScroll, /scrollParent/u, "嵌套滚动容器必须使用自己的可视边界");
assert.match(trainingPage, /mergeUniqueById/u, "分页结果必须按 ID 去重");
assert.doesNotMatch(`${app}\n${trainingPage}`, />\s*(加载下一页|加载更多|上一页|下一页)\s*</u, "长列表不能要求用户手动翻页");

console.log("uiContracts: all checks passed");
