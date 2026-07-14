# Interview Agent Desktop

Electron 桌面端子工程，负责对话 UI、状态面板和本地 API 调用。
Renderer 使用 React + Vite，Electron 负责本地窗口、IPC 和后端 API 代理。

桌面端当前是简历驱动面试工作台：左侧可以导入 PDF / Markdown 简历，也可以填写姓名、目标岗位、级别、简历摘要、完整简历、项目经历和面试目标；右侧进行中文对话。创建会话时这些字段会传给本地 FastAPI，后端 Harness 会结合 RAG 知识库、历史记忆和可选联网搜索生成面试问题、阶段判断和追问。

模式：

- `Agent 面试我`：用户作为候选人回答，Agent 作为面试官追问。
- `Agent 回答我`：用户作为面试官提问，Agent 作为候选人回答。

行业当前只开放 `互联网行业`。

简历库：

- 上传 PDF / Markdown 后会保存到 `.interview_agent/resumes`。
- 相同文件按内容 hash 去重，不会每次重复保存。
- 可以上传多份简历，并在“当前简历”下拉框中选择本轮面试使用哪一份。

## Install

从仓库根目录安装桌面端依赖：

```bash
npm --prefix apps/desktop install
```

依赖会安装在：

```text
apps/desktop/node_modules
```

## Run

桌面端依赖本地 API：

```bash
make api
make desktop
```

React 前端开发态：

```bash
npm --prefix apps/desktop run dev
INTERVIEW_RENDERER_DEV_URL=http://127.0.0.1:5173 npm --prefix apps/desktop run desktop
```

普通 Electron 启动会加载构建产物：

```bash
npm --prefix apps/desktop run build
npm --prefix apps/desktop run desktop
```

## Layout

```text
apps/desktop/
  index.html
  vite.config.js
  package.json
  package-lock.json
  src/
    main.js
    preload.js
    renderer/
      App.jsx
      styles.css
```
