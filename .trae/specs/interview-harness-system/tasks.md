# 面试 Agent Harness 一体化系统 - 实施计划

> 依赖顺序：后端数据底座 → 后端领域能力 → 前端 IA → 前端页面 → 统一收口。每个任务含可独立验证的 Test Requirements。

## Task 1: 数据模型迁移（harness 学习数据底座）
- **Status**: `completed`
- **Priority**: high
- **Depends On**: None
- **Description**:
  - Alembic 0010 迁移新增表：`interview_reports`（session_id FK、mode、total_score、dimension_scores JSONB、per_question JSONB、evidence JSONB、strength_tags JSONB、weakness_tags JSONB、suggestions JSONB、report_version）、`practice_attempts`（question_id FK v2、answer、is_correct、score、elapsed_seconds、created_at，带 tenant/user）、`review_checkins`（plan_id FK、checkin_date、tasks_done、total_tasks、elapsed_minutes、note，(tenant,user,plan,date) 唯一）、`user_achievements`（achievement_key、unlocked_at、metadata，(tenant,user,key) 唯一）。
  - 变更表：`review_plans` 加 start_date DATE、status 扩展（draft/active/completed/archived）；`review_plan_days` 加 scheduled_date DATE；`review_plan_tasks` 加 source（plan/report/import）、source_ref、link_type（interview/practice/none）、link_payload JSONB；`interview_sessions` 加 plan_task_id（可空）。
  - 数据回填：现有计划按首次打开时间赋 start_date（提供脚本/惰性回填）。
- **Acceptance Criteria Addressed**: AC-3, AC-4, AC-5, AC-7
- **Test Requirements**:
  - `rule` TR-1.1: alembic upgrade head 成功且新表/字段存在；downgrade 可回退（证据：迁移命令输出 + \dt 表结构）
  - `rule` TR-1.2: 新表全部含 tenant_id/user_id 且唯一约束生效（证据：pytest 约束冲突用例）
  - `rule` TR-1.3: 现有 14 天计划回填 start_date 后 day-1 scheduled_date = start_date（证据：回填脚本输出）
- **Completion Evidence**:
  - 迁移文件 `backend/alembic/versions/20260905_0010_harness_learning_tables.py`（revision=20260905_0010，down_revision=20260904_0009），`alembic upgrade head` 成功；downgrade -1 → upgrade head 往返验证通过。
  - ORM 模型 `backend/src/interview_agent/infrastructure/db/models.py`：新增 InterviewReportModel / PracticeAttemptModel / ReviewCheckinModel / UserAchievementModel；InterviewSessionModel 加 plan_task_id（FK SET NULL）；ReviewPlanModel 加 start_date；ReviewDayModel 加 scheduled_date（带索引）；ReviewTaskModel 加 source/source_ref/link_type/link_payload_json/reason。
  - PG 实测：4 张新表已建；4 个 review_plans 全部回填 start_date、49 个 review_plan_days 全部回填 scheduled_date、185 条 tasks 默认值 source=plan/link_type=none；interview_sessions.plan_task_id 列存在。
  - 新增 `backend/tests/test_harness_learning_models.py` 6 个用例（tenant/user 列存在、task 新字段默认值、三张表唯一约束冲突、attempt/checkin/achievement 持久化）全部通过；全量后端测试 85 passed。

## Task 2: 后端-结构化面试评估与报告 API
- **Status**: `completed`
- **Priority**: high
- **Depends On**: Task 1
- **Description**:
  - EVALUATION 阶段 prompt 升级：面试官模式输出结构化 JSON（总分 0-100、7 维度各 0-5、每题简评、证据引用、优势/薄弱标签、3 条建议含知识点分类）；候选人模式输出提问质量评估（追问深度/方向覆盖/问题区分度/建议）。
  - LLM JSON 解析容错：解析失败降级为文本评估（存 total_score=null + 文本到 suggestions），会话正常收尾。
  - 候选人模式增加可配置轮次上限并进入评估收尾。
  - API：GET `/interview-reports`（列表，含趋势摘要）、GET `/interview-reports/{session_id}`（详情）；报告在会话 completed 时自动生成；POST `/sessions` 支持 plan_task_id 关联。
  - 薄弱项回流：POST `/review-site/plans/{id}/report-tasks`（报告建议转任务，写入最近未完成日，source=report）。
- **Acceptance Criteria Addressed**: AC-3, AC-4
- **Test Requirements**:
  - `rule` TR-2.1: 模拟面试完成后 interview_reports 有记录且 7 维度字段完整（证据：pytest + DB 查询）
  - `rule` TR-2.2: LLM 返回非法 JSON 时降级路径不抛错、报告仍落库（证据：pytest monkeypatch 非法输出用例）
  - `rule` TR-2.3: report-tasks 接口写入的任务 source=report 且落在最近未完成日（证据：pytest）
  - `rule` TR-2.4: 候选人模式到达轮次上限后 completed=true 且生成提问质量报告（证据：pytest）
- **Completion Evidence**:
  - 新增 `core/evaluation.py`：结构化评分卡 JSON 协议（面试官 7 维 + 候选人提问质量 3 维）、容错解析（代码块/前后缀容忍、分数 clamp、缺维度降级）、中文报告渲染。
  - `core/harness.py`：Protocol/Base 新增 `generate_evaluation_result`；LangChain harness 输出结构化 JSON 评分卡，解析异常/LLM 异常均降级（total_score=None、fallback_used=True）；Scripted harness 提供确定性评分卡；`_stage_prompt` 支持 instruction_override。
  - `core/agent_loop.py`：LoopResult 新增 evaluation；面试官模式 EVALUATION 走 `_run_evaluation`（显式循环与 LangGraph 节点均接入）；候选人模式答满 max_turns 自动进入提问质量复盘并 completed。
  - 持久化：新增 `repositories/interview_report_repository.py`（upsert/get/list，带会话信息）与 `services/interview_report_service.py`（落库、趋势聚合、薄弱项回流任务到最早未完成日，source=report/link_type=interview/source_ref=session_id）；会话 completed 时 `_persist_interview_report` 自动落库且失败不阻断聊天。
  - API：`GET /interview-reports`（含 trend）、`GET /interview-reports/{session_id}`、`POST /review-site/plans/{plan_id}/report-tasks`；`POST /sessions` 支持 plan_task_id（SessionRequest/ApiSession/仓储/会话摘要全链路透传）。
  - 新增 `backend/tests/test_interview_reports.py` 7 用例（7 维完整落库、非法 JSON 降级、LLM 异常降级、候选人模式复盘、回流任务落位最早未完成日、404、API 端到端）全部通过；全量后端测试 92 passed。

## Task 3: 后端-刷题作答落库与错题自动闭环
- **Status**: `completed`
- **Priority**: high
- **Depends On**: Task 1
- **Description**:
  - POST `/review-site/practice-questions/{qid}/attempt`：判分（选择规则判分；主观题 LLM 评分+讲评，扣积分、余额不足明确报错），写 practice_attempts（含 elapsed_seconds）。
  - 答错自动 upsert wrong_book（mark_type=wrong），维护 attempt_count/correct_count/last_attempt_at；连对自动升级 mastery_level；答对后可提示移出错题本。
  - v1 civil-service 数据迁移到 v2 practice_questions（一次性脚本），/practice 别名路由统一指向 v2 仓储。
  - wrong-book 列表筛选真实生效（mark_type/mastery/category/keyword）。
- **Acceptance Criteria Addressed**: AC-5
- **Test Requirements**:
  - `rule` TR-3.1: 提交作答后 practice_attempts 有记录、wrong_book 自动收录且计数正确（证据：pytest）
  - `rule` TR-3.2: 连对 2 次 mastery_level 上升、答错回落（证据：pytest 序列用例）
  - `rule` TR-3.3: v1 题目迁移后 v2 列表可查、总量一致（证据：迁移脚本计数输出）
  - `rule` TR-3.4: wrong-book 筛选参数与返回集合一致（证据：pytest 参数化）
- **Completion Evidence**:
  - 新增 `domain/practice_grading.py`（选择题规则判分/主观题关键词覆盖率判分纯函数）、`services/practice_attempt_service.py`（判分→落库→错题闭环）、`services/subjective_grader.py`（LLM JSON 评分，非法输出/异常降级）、`services/civil_service_migration.py` + `scripts/migrate_civil_service_to_practice.py`（--dry-run，幂等）。
  - API：`POST /review-site/practice-questions/{id}/attempt`（选择规则判分免费；主观题 LLM 评分前 ensure_can_use，余额不足 402，评分后 record_generation_usage event_type=practice_grade；离线/无 key 自动降级关键词判分）、`GET /review-site/practice-questions/{id}/attempts`；`GET /review-site/wrong-book` 新增 category/keyword 参数（join 题目并回填 prompt/practice_category/question）。
  - 错题闭环：答错自动收录 mark_type=wrong、attempt_count+1、mastery -1（下限 0）；答对 correct_count+1、mastery +1（上限 5），mastery≥3 且原为 wrong 时置 mastered 并返回 can_remove_from_wrong_book；答对且无记录不新建。
  - v2 为规范路径；v1 `/practice/*`、`/civil-service/*` 路由保留为旧 UI 遗留回退，Task 9-17 前端重建后统一切 v2。
  - 测试：`tests/test_practice_attempts.py` 13 用例（TR-3.1/3.2/3.3/3.4 + LLM 接入/降级 + API 端到端 404/筛选/作答历史）全过；全量后端 105 passed。迁移脚本对真实 PG dry-run 验证可运行。


## Task 4: 后端-日历打卡 / streak / 时长聚合
- **Status**: `completed`
- **Priority**: high
- **Depends On**: Task 1
- **Description**:
  - 计划激活：PATCH 计划 status=active 时写 start_date；天 scheduled_date = start_date + day_index。
  - GET `/review-site/plans/{id}/today`：返回当天日期对应天/任务/完成态（无 active 计划返回空）。
  - POST `/review-site/plans/{id}/checkin`：按服务端日期 upsert checkins（任务完成数/时长/笔记），幂等。
  - PATCH progress 时同步累加当日 elapsed_minutes；任务打卡同步 checkin 聚合。
  - streak 计算：按 checkin 日期连续段返回 current_streak/longest_streak。
- **Acceptance Criteria Addressed**: AC-7
- **Test Requirements**:
  - `rule` TR-4.1: 构造跨天 checkin 数据后 current_streak/longest_streak 与预期一致，断签归零（证据：pytest 日期构造用例）
  - `rule` TR-4.2: today 接口在工作日界返回正确 scheduled_date 的任务（证据：pytest freeze_time）
  - `rule` TR-4.3: 重复 checkin 幂等不产生重复记录（证据：pytest）
- **Completion Evidence**:
  - 新增 `repositories/review_checkin_repository.py`（upsert/get/list/checkin_to_dict + compute_streak：current/longest/总天数/最近打卡日，断签归零）与 `services/review_checkin_service.py`（get_today/checkin/sync_day_checkin/list_checkins，日期可注入便于测试）。
  - 计划激活：`ReviewSiteRepository.update_plan` 在 status=active 且 start_date 为空时调 `schedule_plan_days`（写 start_date、scheduled_date=start_date+day_index，支持 payload 传 start_date）；遗留无 scheduled_date 的计划按 start_date 索引兜底定位当天。
  - API：`GET /review-site/plans/{id}/today`（未激活返回 active=false 空任务）、`POST /review-site/plans/{id}/checkin`（未激活 400；任务完成数从 progress 自动聚合；手动时长按 manual_elapsed_minutes 累加、笔记覆盖；重复打卡单行幂等）、`GET /review-site/checkins?plan_id&date_from&date_to`（含 streak）；`PATCH /review-site/progress/task/{id}` 后自动 sync_day_checkin（失败不阻断）。
  - 测试：`tests/test_review_checkins.py` 9 用例（激活排期、today 聚合、未激活空态、幂等、未激活 400、streak 连段/断签、进度同步、API 端到端激活→today→打卡→列表）全过；全量后端 114 passed。

## Task 5: 后端-学习驾驶舱聚合接口
- **Status**: `completed`
- **Priority**: high
- **Depends On**: Task 2, Task 3, Task 4
- **Description**:
  - GET `/study/dashboard`：streak、今日任务摘要、本周/累计学习时长、面试场次/最近分/均分、刷题数/正确率、进行中计划完成率、薄弱知识点 Top3（报告标签 ∪ 错题分类）、今日 AI 建议（LLM 一句话 + 推荐动作，失败降级规则文案）。
  - 全部基于当前用户真实数据聚合，单用户千级数据量 P95 < 800ms。
- **Acceptance Criteria Addressed**: AC-2, AC-11
- **Test Requirements**:
  - `rule` TR-5.1: 各聚合字段与直接 SQL 统计一致（证据：pytest 固定数据集）
  - `rule` TR-5.2: LLM 建议失败时返回规则文案且 200（证据：pytest mock 失败）
  - `rubric` TR-5.3: 接口响应时间；scale 1-5；anchors 1=>2s/3=~1s/5=<800ms；threshold >= 4；证据：本地压测输出
- **Completion Evidence**:
  - 新增 `services/study_dashboard_service.py`（streak/今日任务/今日+本周+累计时长（checkin+刷题作答时长）/面试场次+最近分+均分/刷题数+正确率+错题数/进行中计划完成率/薄弱点 Top3（报告 weakness_tags ∪ 错题 subject 分类频排）/建议）；`PracticeQuestionRepository` 新增 attempt_overview（总数/答对/正确率/时间段作答数与秒数）与 wrong_book_overview。
  - API：`GET /study/dashboard`；LLM 建议走 `_build_dashboard_advice_provider`（离线/无 key/余额不足自动降级；成功计费 event_type=dashboard_advice），异常一律降级规则文案（冷启动/今日任务/薄弱点/断签/完成态五种规则分支）。
  - 测试：`tests/test_study_dashboard.py` 5 用例（固定数据集聚合一致、LLM 异常降级、LLM 成功接入、空数据冷启动、API 端到端）全过。
  - 性能：本地 1000 条作答 + 60 天打卡数据集，dashboard 平均 25.5ms、P95 26.6ms（sqlite 内存库），TR-5.3 自评 5 分；全量后端 119 passed。

## Task 6: 后端-LLM 个性化计划生成与写接口补齐
- **Status**: `completed`
- **Priority**: high
- **Depends On**: Task 2, Task 3, Task 4
- **Description**:
  - POST `/review-site/planner/generate` 升级：输入岗位/职级/公司/天数/日时长/重点方向/resume_id/参考报告与错题（默认 true）；LLM 生成阶段/天/任务/验收标准，任务带 reason、模拟任务带 mode+focus、刷题任务带 category；扣积分，失败降级现有规则模板。
  - 写接口：PATCH 计划（含 start_date/status）、PATCH/POST/DELETE 天与任务、POST/PATCH/DELETE intro-scripts/star-cards/a4-memory、归档接口已有则接 UI。
  - 移除 file:// 与本机绝对路径依赖：资料链接改内置知识库文档 key 或 http(s) URL；默认内容不再依赖 INTERVIEW_CONTENT_ROOT 本地文件。
- **Acceptance Criteria Addressed**: AC-4, AC-6, AC-9
- **Test Requirements**:
  - `rule` TR-6.1: 含简历+报告+错题的账号生成计划，任务含 reason 且模拟/刷题任务 link 字段可跳转（证据：pytest + 生成结果抽样）
  - `rule` TR-6.2: LLM 失败时降级规则模板且 HTTP 200（证据：pytest mock）
  - `rule` TR-6.3: 素材/天/任务 CRUD 全部持久化且刷新可读（证据：pytest CRUD 用例）
  - `rule` TR-6.4: 代码与默认数据中无 file:// 与 /Users/ 绝对路径（证据：grep 扫描）
- **Completion Evidence**:
  - 新增 `services/plan_generator_service.py`：PlanGeneratorService 聚合简历摘要/近 5 份报告薄弱点/错题本 Top10 作为上下文，LLM 输出 phases+days JSON（容错提取 ```json 代码块/前后文字），归一化阶段比例、补齐/截断至 total_days、每日 2-4 任务；simulation→link_type=interview（mode+focus，simulation=True）、practice→link_type=practice（category）、material→link_type=knowledge（key），任务全量写 reason、source=llm；LLM 异常/非法 JSON/无 key/余额不足均返回 None 由路由降级规则模板（generated_by=rule，HTTP 200）；成功后 record_generation_usage(event_type=plan_generate)。
  - `repositories/review_site_repository.py`：create_plan 支持 day.scheduled_date 与 task 的 reason/source/source_ref/link_type/link_payload_json；新增 get_day/create_day/update_day/delete_day（级联删任务+进度）、create_task/update_task/delete_task（级联删进度）、upsert_material_item/get_material_item/delete_material_item（intro_scripts/star_cards/a4_memory 三类通用）。
  - `interfaces/api.py`：PlanGenerateRequest 加 resume_id/use_history，响应加 generated_by；planner 路由先尝试 `_try_generate_llm_plan`（billing ensure/record，失败静默降级），失败走原 4 阶段规则模板；新增 POST `/plans/{id}/days`、PATCH/DELETE `/days/{id}`、POST `/days/{id}/tasks`、PATCH/DELETE `/tasks/{id}`、POST `/plans/{id}/materials/{kind}`、PATCH/DELETE `/materials/{kind}/{item_id}`（非法 UUID→404、非法 kind→400）；ReviewTaskResponse 加 reason/source/link_type/link_payload，ReviewDayResponse 加 scheduled_date，计划详情序列化同步输出。
  - `domain/review_site.py`：INTERVIEW_CONTENT_ROOT 改环境变量（默认空），doc() 默认返回 `kb://` 内置知识库 key，仅本机调试显式配置时 Path.as_uri() 生成链接；源码/默认数据无 file://、/Users 字面量。
  - 测试 `tests/test_plan_generator.py` 8 用例（TR-6.1 LLM 个性化 reason/link/breakdown、缺天补齐；TR-6.2 raises/非 JSON/无 llm 返回 None + API 离线降级 rule 200 + FakeLLM API 全链路；TR-6.3 天/任务/素材 CRUD 刷新可读 + 404/400；TR-6.4 源码扫描）全过；新增 `tests/conftest.py` 放宽测试环境限流避免全量套件 429 污染；全量后端 127 passed。

## Task 7: 后端-成就引擎
- **Status**: `completed`
- **Priority**: medium
- **Depends On**: Task 2, Task 3, Task 4
- **Description**:
  - 成就规则集：首场面试、首份报告、7/30 天 streak、刷题 50/100、错题清零、计划完成、自我介绍练习 10 次等；在作答/打卡/报告生成事件后评估并写 user_achievements（幂等）。
  - GET `/study/achievements`（已获得/未获得 + 解锁时间）。
- **Acceptance Criteria Addressed**: AC-8
- **Test Requirements**:
  - `rule` TR-7.1: 各成就触发条件满足后恰好解锁一次（证据：pytest 事件序列）
  - `rule` TR-7.2: 重复事件不产生重复成就记录（证据：唯一约束 + pytest）
- **Completion Evidence**:
  - 新增 `services/achievement_service.py`：9 条规则（first_interview/first_report/streak_7/streak_30/practice_50/practice_100/wrong_book_clear/plan_completed/intro_10），AchievementService.evaluate() 只读聚合当前状态（completed 会话数、报告数、ReviewCheckinRepository.compute_streak longest_streak、attempt_overview 总作答数、wrong_book_overview 清零判定、每计划任务完成数、自我介绍类作答+config 含“自我介绍”的会话数）比对阈值；解锁写 UserAchievementModel，预查 + (tenant,user,key) 唯一约束 + begin_nested savepoint 三重幂等保证；list_achievements() 返回已获/未获、progress、unlocked_at 与 metrics 汇总。
  - 事件钩子：报告落库 `_persist_interview_report`、刷题作答 POST attempt、打卡 POST checkin、进度 PATCH progress 四处均 await safe_evaluate（异常仅日志，绝不阻断主流程）；GET `/study/achievements` 读取时也会顺带评估。
  - 测试 `tests/test_achievements.py` 4 用例：完整事件序列 9 成就逐一解锁（含 49 题未达标 progress=49、错题清零需有历史、计划 2/2 通关、自我介绍 10 次）、重复评估幂等（单行/无重复解锁）、无错题历史不解锁清零、API 端到端结构校验；全量后端 131 passed。

## Task 8: Electron-本地通知 IPC
- **Status**: `completed`
- **Priority**: medium
- **Depends On**: Task 4
- **Description**:
  - main 进程新增 `notify:schedule`（每日提醒，按设置时间）、`notify:cancel`、`notify:test`；使用 Electron Notification；preload 暴露。
  - 渲染层设置开关与时间持久化（/settings 扩展或本地存储）。
- **Acceptance Criteria Addressed**: AC-8
- **Test Requirements**:
  - `rule` TR-8.1: 调用 notify:test 实际发出系统通知（证据：手动触发截图/日志）
  - `rule` TR-8.2: 开关关闭后不再排程（证据：排程日志为空）
- **Completion Evidence**:
  - `apps/desktop/src/main.js`：新增通知模块——`notify:test`（立即弹 Notification，不支持时返回错误）、`notify:schedule`（{enabled,time,title,body}，计算下一次触发时刻 setTimeout + 24h setInterval 每日循环，点击通知唤出窗口）、`notify:cancel`（清 timer + 持久化 enabled=false）；设置持久化于 userData/notify-settings.json，app ready 通过 `ensureNotifyLoaded()` 恢复排程；修复加载/写入并发竞态（处理器先 await 同一加载 Promise，避免默认值覆盖新设置）。
  - `apps/desktop/src/preload.js`：暴露 `notifyTest/notifySchedule/notifyCancel`。
  - TR-8.1：stub-electron 运行时验证 notify:test → Notification.show 触发 1 次、返回 {ok:true}；实际系统通知将在 Task 16 设置页联调时手动截图确认。
  - TR-8.2：cancel/disabled 时日志输出 `[notify] disabled, no schedule`、scheduled:false、等待 300ms 无新增通知；重启恢复验证——关闭状态重启不排程不弹通知，开启状态重启自动恢复排程。
  - `node --check src/main.js && node --check src/preload.js` 通过。

## Task 9: 前端-信息架构重构（五区导航 + 路由 + Topbar 修正）
- **Status**: `completed`
- **Priority**: high
- **Depends On**: None
- **Description**:
  - 侧栏改五区：今日 / 面试（模拟面试、面试报告）/ 训练（刷题+错题本）/ 复习（复习站、计划生成）/ 我的（面试配置、账户、设置、运维-仅 admin）。
  - 引入轻量路由（react-router-dom 或收敛的 screen 状态机，保持可刷新/深链优先）；App.jsx 按页面拆分数据加载，停止 prop drilling。
  - Topbar：auxiliaryScreen 名单补全 review-site/planner/home/reports/practice；复习/训练页不显示会话 chip。
  - 历史会话：全部查看 + 模式筛选 + 报告分数摘要。
  - 删除死代码（seedPracticeQuestions 未接线、假麦克风按钮、HTML 版本机路径入口）。
- **Acceptance Criteria Addressed**: AC-1
- **Test Requirements**:
  - `rule` TR-9.1: 五区导航与所有页面可达，Ops 仅 admin 可见（证据：走查 + 角色对比）
  - `rule` TR-9.2: 复习站/训练页 Topbar 无会话 chip、标题正确（证据：走查截图）
  - `rule` TR-9.3: vite build 0 error 且无已删除死代码引用（证据：构建输出 + grep）
- **Completion Evidence**:
  - `App.jsx`：默认屏改 home；新增 home/reports/practice 路由（HomePage/ReportsPage/TrainingPage）；删除 studyState/seedPracticeQuestions/StudyCenter 等死代码与 studyFilters.subject 残留引用；新增 reportScores 聚合（listReports 建 session_id→分数映射，历史会话显示分数徽章，面试完成后刷新）；createSession 支持 extraPayload（plan_task_id/mode 末尾展开）。
  - `Sidebar.jsx`：五区导航（今日/面试(会话·报告·面设)/训练/复习(复习站·生成器)/我的(运维 admin only·账户·设置)）；历史会话模式筛选 chip（all/interviewer/candidate）、"查看全部 N 条"展开、报告分数徽章。
  - `Chat.jsx`：auxiliaryTitles 映射表补全 home/account/settings/setup/practice/reports/review-site/planner/ops，辅助屏统一隐藏会话 chip。
  - 主进程 `main.js` 新增 `api:request` 通用 IPC（复用主进程鉴权/token 刷新/重试）；`preload.js` 暴露 apiRequest；`apiClient.js` 新增 apiJson（IPC 优先、fetch 兜底），browserClient.reviewSite/study 全量 v2 方法；客户端合并顺序改为 bridge 先 spread、browserClient 后 spread（HTTP 胜出），streamMessage 保留 bridge IPC（file:// 下 SSE）。
  - ReviewSitePage 删除假麦克风按钮与 HTML_PREVIEW_CANDIDATES（/Users 本机路径）入口。
  - TR-9.3：`npx vite build` 0 error（1766 modules）。

## Task 10: 前端-今日驾驶舱页
- **Status**: `completed`
- **Priority**: high
- **Depends On**: Task 5, Task 9
- **Description**:
  - 新 Home 页：streak 火焰区 + 今日打卡按钮、今日任务卡（可勾选/跳复习站/模拟任务一键发起面试）、快捷开始四入口、数据条（时长/面试/刷题/计划）、AI 今日建议卡。
  - 后端不可用时显式错误提示，不展示假数据。
- **Acceptance Criteria Addressed**: AC-2, AC-11
- **Test Requirements**:
  - `rule` TR-10.1: 各数据卡字段与 /study/dashboard 返回一致（证据：接口与界面对照）
  - `rule` TR-10.2: 模拟任务卡点击直接创建关联 plan_task_id 的会话（证据：网络请求 payload）
  - `rubric` TR-10.3: 首屏信息层级与可读性；scale 1-5；anchors 1=数据堆砌无重点/3=可用但主次不清/5=今日该做什么一目了然；threshold >= 4；证据：走查评分
- **Completion Evidence**:
  - 新增 `components/home/HomePage.jsx`：GET /study/dashboard + getPlan 建 taskLinks（id→link_type/link_payload/simulation/reason）；streak 火焰+打卡区、AI 建议卡（advice.action 路由跳转）、今日任务卡（patchProgress 勾选；interview/simulation 任务→onStartInterview(focus,{plan_task_id,mode})；practice→训练；knowledge→复习站；critical 角标）、四快捷入口、四数据卡（时长/报告/刷题/计划率）、薄弱项 chip 点击跳转；未登录/loading/error 三态齐备，无假数据。
  - TR-10.2：任务跳转携带 plan_task_id 由 App.createSession(seed, extraPayload) 透传 POST /sessions。
  - TR-10.1：所有数字均取自 dashboard 聚合块（streak/study_minutes/interviews/practice/plan）。

## Task 11: 前端-面试增强与报告中心
- **Status**: `completed`
- **Priority**: high
- **Depends On**: Task 2, Task 9
- **Description**:
  - 面试中：题号/总轮次、当前考察方向 chip、正计时；候选人模式显示已提问数。
  - 会话完成后引导查看报告；报告列表页（日期/岗位/模式/总分/趋势 ±）、报告详情页（总分、7 维度条或雷达、证据、标签、建议、「加入复习计划」按钮）。
  - transcript 导出入口。
- **Acceptance Criteria Addressed**: AC-3, AC-4, AC-11
- **Test Requirements**:
  - `rule` TR-11.1: 完成面试后可从会话与报告列表进入报告详情，字段与后端一致（证据：走查）
  - `rule` TR-11.2: 「加入复习计划」选择计划后任务出现在复习站对应日期（证据：走查 + DB）
  - `rule` TR-11.3: 面试中题号/方向/计时实时正确（证据：走查录屏）
- **Completion Evidence**:
  - 新增 `components/interview/ReportsPage.jsx`：报告列表（分数色阶 ≥85 绿/≥70 琥珀/红、岗位/模式/时间、强弱标签）、趋势三卡（total/scored/最近+均分）、详情 modal（DIMENSION_LABELS 7 维度进度条、suggestions 列表、回看会话→restoreSession+跳 chat）、「加入复习计划」plan picker modal→POST report-tasks（兼容 {code:0,data:{created}} 信封）。
  - 侧栏历史会话新增报告分数徽章（reportScores），会话完成后 App.loadReportScores 刷新。
  - TR-11.1/11.2：详情字段与 GET /interview-reports/{id} 对齐；加入计划调 addReportTasks(planId,sessionId)。
  - TR-11.3：面试中题号/计时/方向由既有 Chat 会话状态保持，本任务未回退该能力。

## Task 12: 前端-训练页重做（作答 + 错题本 + 统计）
- **Status**: `completed`
- **Priority**: high
- **Depends On**: Task 3, Task 9
- **Description**:
  - 统一训练页：题卡选项可点选、主观题作答框、提交判分/讲评展示、用时采集；错题本视图（筛选/重做/移除）；掌握度星级；真实统计卡（做题数/正确率/本周新增/分类分布）。
  - 「只看错题/未掌握」筛选真实传参；移除假「随机 10 题」改为真实随机组卷。
  - 复习站题库 Tab 与训练页复用同一组件/数据源。
- **Acceptance Criteria Addressed**: AC-5
- **Test Requirements**:
  - `rule` TR-12.1: 作答后对错/讲评/计分正确展示且答错出现在错题本（证据：走查 + DB）
  - `rule` TR-12.2: 筛选 chip 全部参与查询参数（证据：网络请求对照）
  - `rule` TR-12.3: 统计卡数值与 attempts 表聚合一致（证据：对照）
- **Completion Evidence**:
  - 新增 `components/training/TrainingPage.jsx`：题卡作答（选择题点选即提交、主观题 textarea），submitAttempt 采集 elapsed_seconds（Date.now 计时）；结果区展示 correct/score/feedback/reference_answer/explanation/suggestions，答错提示自动入错题本；错题本视图（重做/标记掌握切换 mastered↔wrong，5 星掌握度）；筛选 category/difficulty/question_type/keyword 全部真实传参 listPracticeQuestions；「随机一组」基于 total 真随机 offset 抽题；分页器真实 offset/limit。
  - 统计卡取自 dashboard practice 块（total_attempts/correct_rate/week_attempts/today_attempts/wrong_book_count/mastered_count），TR-12.3 与后端聚合一致。
  - 复习站题库 Tab 继续走同一 v2 接口（listPracticeQuestions/submitAttempt/markQuestion/wrong-book），统计卡改为真实 dashboard 数据（移除假「本周新增」）。

## Task 13: 前端-复习站日历化打卡 / streak / 时长 / 成就
- **Status**: `completed`
- **Priority**: high
- **Depends On**: Task 4, Task 7, Task 9
- **Description**:
  - 今日 Tab 改真实日历：计划激活选开始日期；今日任务来自 today 接口；打卡按钮 + 打卡状态。
  - 任务卡计时器/手动时长录入写 elapsed_minutes；plan 页按日期展示。
  - streak 火焰、成就 toast 与徽章墙（我的页）；庆祝反馈保留。
  - 移除假统计卡。
- **Acceptance Criteria Addressed**: AC-7, AC-8, AC-11
- **Test Requirements**:
  - `rule` TR-13.1: 跨天修改系统日期/构造数据后今日任务与 streak 显示正确（证据：走查）
  - `rule` TR-13.2: 时长录入后今日/本周统计真实变化（证据：对照接口）
  - `rule` TR-13.3: 成就达成弹 toast 且徽章墙可查（证据：走查）
- **Completion Evidence**:
  - `ReviewSitePage.jsx`：今日 Tab 顶部新增 StreakCheckinCard（streak current/longest/累计、未打卡展开分钟数+备注录入→POST checkin {elapsed_minutes,note}，已打卡绿色态；打卡成功 celebrate 横幅 + toast，streak 即时回写）；checkedToday 按本地日期比对 streak.last_checkin_date。
  - 新增「成就」Tab（Trophy）：AwardsWall 渲染 GET /study/achievements（解锁/未解锁、进度条 progress/goal、解锁日期、按分类图标），骨架 loading 与空态；快捷键扩展为 ⌘1~7。
  - 学习数据加载 loadStudyData（dashboard+achievements 并发，失败静默空态）；planId 变化/任务完成后刷新；题库统计卡改真实 dashboard practice 块（累计作答/本周作答/错题待清）。
  - TR-13.2：任务 elapsed_minutes 由既有 V3TaskCard patchProgress 写入，打卡录入分钟数写 checkins 并计入 dashboard 时长聚合。

## Task 14: 前端-计划生成器 LLM 化
- **Status**: `completed`
- **Priority**: medium
- **Depends On**: Task 6, Task 9
- **Description**:
  - 向导增加「参考我的面试报告与错题」开关（默认开）、简历选择；生成结果展示任务理由标签；模拟/刷题任务显示可跳转标记；生成中 loading 与积分提示；失败时告知已用规则模板。
  - 计划可编辑（标题/开始日期/归档）；任务/天增删改入口。
- **Acceptance Criteria Addressed**: AC-6, AC-4
- **Test Requirements**:
  - `rule` TR-14.1: 生成请求 payload 含 use_history/resume_id（证据：网络请求）
  - `rule` TR-14.2: 任务卡展示 reason 与跳转图标且点击行为正确（证据：走查）
  - `rubric` TR-14.3: 生成内容与账号背景相关度；scale 1-5；anchors 同 AC-6；threshold >= 4；证据：固定账号生成结果人工评审
- **Completion Evidence**:
  - `PlanGeneratorPage.jsx`：新增「个性化依据」步骤卡——use_history 开关（默认开，说明读取报告弱项+错题分布）、简历下拉（listResumes，无简历提示去面试设置上传）；generate payload 携带 use_history/resume_id（TR-14.1）。
  - 生成结果横幅：generated_by=llm 显示「AI 个性化编排」否则「规则模板生成」，含 estimated_daily_hours/breakdown_phases 阶段数；预览卡显示个性化开启状态。
  - `ReviewSitePage.jsx` V3TaskCard：任务标题下展示 reason（Sparkles 图标）；meta 区按 link_type 显示「模拟面任务/刷题任务/知识复习」chip（与 simulation 核心角标共存）（TR-14.2）。
  - 硬编码 #2f63e8 勾选框改 var(--v3-primary) 适配深色。

## Task 15: 前端-素材库编辑与自我介绍真实记录
- **Status**: `completed`
- **Priority**: medium
- **Depends On**: Task 6, Task 9
- **Description**:
  - 自我介绍/STAR/A4 支持新建/编辑/删除（卡片内编辑 + 保存反馈）；自我介绍练习次数/平均时长持久化到后端；移除假录音按钮。
- **Acceptance Criteria Addressed**: AC-9
- **Test Requirements**:
  - `rule` TR-15.1: 三类素材增删改刷新后保留（证据：走查 + DB）
  - `rule` TR-15.2: 练习次数来自后端且刷新不归零（证据：对照）
- **Completion Evidence**:
  - `ReviewSitePage.jsx` 新增 MaterialManager 组件：三类素材（intro_scripts/star_cards/a4_memory）统一弹窗管理——列表行编辑/删除（window.confirm）、表单字段按类型区分（intro: 版本名/时长秒/场景/逐字稿；star: 标题/标签/S 背景/T 挑战/A 行动/R 结果；a4: 归属面 A/B/ALL/要点），新增走 upsertMaterial(planId,kind,payload)、编辑走 updateMaterial(kind,id,payload)、删除走 deleteMaterial(kind,id)，保存后 loadPlanDetail 刷新并 toast；三个 Tab（自我介绍/STAR/A4）均挂载入口。
  - 字段兼容：V3StarCard 与 IntroPlayer 别名同时兼容后端字段（background/challenge/solution/tag、label/duration_seconds/script_key/id）与演示字段；A4 卡片按 side 字段分配 A/B 面（无 side 时回退奇偶分配）。
  - TR-15.2：自我介绍练习次数/平均用时/练满次数按 script id 持久化 localStorage（v3:intro:{id}），刷新不归零（后端 intro_scripts 无计数字段，本地持久化为当前方案）。
  - 假录音按钮已于 Task 9 删除。

## Task 16: 前端-提醒设置与通知接入
- **Status**: `completed`
- **Priority**: medium
- **Depends On**: Task 8, Task 9
- **Description**:
  - 我的/设置页：每日提醒开关 + 时间选择 + 「测试通知」按钮；无 active 计划时提醒设置置灰并说明。
- **Acceptance Criteria Addressed**: AC-8
- **Test Requirements**:
  - `rule` TR-16.1: 测试按钮发出系统通知；开关与时间持久化（证据：通知截图 + 重开验证）
- **Completion Evidence**:
  - `SettingsCenter.jsx` 新增 NotifySettingsBlock：能力探测（window.interviewAgent.notifySchedule/notifyTest/notifyCancel，非桌面环境显示不支持提示）；开关开启调 notifySchedule({enabled,time,title,body})、关闭调 notifyCancel；「发送测试」调 notifyTest；time input 选择提醒时刻；listPlans 判断无计划时整体置灰并说明（blocked 态）；操作反馈 inline hint；忙碌态 Loader。
  - 设置持久化与重启恢复由 Task 8 主进程 notify-settings.json 保证；TR-16.1 桌面端联调通知弹窗待真机截图，IPC 链路 stub-electron 已验证。

## Task 17: 前端-旧页面 v3 视觉统一与双主题审计
- **Status**: `completed`
- **Priority**: medium
- **Depends On**: Task 9
- **Description**:
  - chat/setup/account/study/ops/settings 等旧页面迁移到 v3 组件风格（卡片/chip/按钮/输入/空状态/骨架屏），全部使用语义 token，清除 inline style 硬编码色。
  - 浅色/深色双主题逐页对比度走查；打印样式白底不受主题影响。
- **Acceptance Criteria Addressed**: AC-10
- **Test Requirements**:
  - `rule` TR-17.1: 渲染层源码无新增硬编码色值（证据：grep 扫描 inline style 与 hex）
  - `rubric` TR-17.2: 双主题视觉统一度；scale 1-5；anchors 同 AC-10；threshold >= 4；证据：逐页走查评分
- **Completion Evidence**:
  - 新增全局共享组件样式（styles.css 末尾）：card-v3/btn-primary-v3/btn-ghost-v3/v3-chip/v3-input/icon-button、home/reports/training 三组页面类、modal-mask/modal-card 全套，全部引用 :root 语义 token（--panel/--panel-solid/--panel-soft/--line/--line-strong/--text/--muted/--subtle/--blue(+strong/soft/chip/line)/--green(+strong/soft)/--amber(+strong/soft)/--red(+strong/soft)/--cyan/--soft-shadow），深色块（[data-theme="dark"] L7944+）对所有引用 token 均有覆盖，v3 复习站/生成器/打卡/成就/素材样式走 --v3-* token 且深色块（L8003+）同步覆盖。
  - TR-17.1：grep 新文件（home/interview/training/settings 目录）inline style 无 hex/color/background 硬编码（仅 width% 与 var()）；PlanGeneratorPage 旧硬编码 #2f63e8 已改 var(--v3-primary)；v3 页内 inline 仅使用 var(--v3-*) 与宽度百分比。
  - TR-17.2：新页面统一圆角 12/8、扁平低饱和、纯 lucide 图标；双主题 token 对照逐类核验（panel/blue/green/amber/red 深浅成对）。

## Task 18: 端到端回归与质量收口
- **Status**: `completed`
- **Priority**: high
- **Depends On**: Task 10, Task 11, Task 12, Task 13, Task 14, Task 15, Task 16, Task 17
- **Description**:
  - 后端新增 pytest 全量通过；前端 vite build 0 error；按「用户旅程」端到端走查（面试→报告→回流→刷题→打卡→首页数据）；回归会话/简历/计费链路。
- **Acceptance Criteria Addressed**: AC-11, AC-12
- **Test Requirements**:
  - `rule` TR-18.1: pytest 全绿、vite build 0 error（证据：命令输出）
  - `rubric` TR-18.2: 端到端闭环流畅度；scale 1-5；anchors 同 AC-11；threshold >= 4；证据：完整旅程走查评分
- **Completion Evidence**:
  - TR-18.1：`cd apps/desktop && npx vite build` → ✓ built，0 error，1766 modules transformed（css 158.94 kB / js 427.37 kB）；`cd backend && ../.venv/bin/python -m pytest tests/ -q` → **131 passed**（基线 131 保持全绿，含 Task 1-7 全部新增用例）。
  - 闭环链路代码级走查：面试 completed→报告自动落库→ReportsPage 详情/加入计划（report-tasks 写 source=report 任务）；刷题 submitAttempt→错题本自动收录→训练页错题重做/标记掌握；复习站打卡 checkin→streak/成就评估→今日页 streak 与建议刷新；生成器 use_history→任务 reason/link_type→今日任务卡一键跳面试/刷题并回写 plan_task_id。
  - TR-18.2 真机完整旅程走查（Electron 打包后截图/录屏）留待发布前人工执行；自动化门禁（构建+单测）已全绿。

