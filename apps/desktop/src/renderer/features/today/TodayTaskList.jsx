import { BookOpenCheck, CircleAlert, Loader2, MessageSquarePlus, PenLine, PlayCircle, Wand2 } from "lucide-react";

const TYPE_LABELS = {
  interview: "模拟",
  practice: "刷题",
  material: "资料",
  checkin: "打卡",
  review: "复习"
};

export function TodayTaskList({ today, tasks, busyTask, readOnly = false, onToggle, onStart, onOpen, onNavigate, onStartInterview }) {
  const progress = today?.total_tasks ? Math.round((today.tasks_done / today.total_tasks) * 100) : 0;
  return (
    <section className="home-today card-v3">
      <div className="home-section-head">
        <div>
          <h3>今日任务</h3>
          <p>{today?.plan_title ? `来自计划「${today.plan_title}」` : "还没有进行中的复习计划"}</p>
        </div>
        <div className="home-today-summary">
          <span>{today?.tasks_done || 0}/{today?.total_tasks || 0} 完成</span>
          <div className="home-progress-bar"><div style={{ width: `${progress}%` }} /></div>
        </div>
      </div>
      {tasks.length === 0 ? (
        <div className="home-empty-tasks">
          <p>今天没有安排任务。生成一个计划，或直接开始一场模拟面试。</p>
          <div className="home-empty-actions">
            <button type="button" className="btn-primary-v3" onClick={() => onNavigate?.("planner")} disabled={readOnly}>
              <Wand2 size={14} /> 生成复习计划
            </button>
            <button type="button" className="btn-ghost-v3" onClick={() => onStartInterview?.("", {})} disabled={readOnly}>
              <MessageSquarePlus size={14} /> 直接开始面试
            </button>
          </div>
        </div>
      ) : (
        <ul className="home-task-list">
          {tasks.map((task) => (
            <TaskRow
              key={task.id}
              task={task}
              busy={busyTask === task.id}
              disabled={readOnly || Boolean(busyTask)}
              onToggle={onToggle}
              onStart={onStart}
              onOpen={onOpen}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function TaskRow({ task, busy, disabled, onToggle, onStart, onOpen }) {
  const actionable = task.primary_action?.command === "start";
  const rejected = task.verification?.status === "rejected";
  const Icon = task.task_type === "interview" ? PlayCircle : task.task_type === "practice" ? PenLine : BookOpenCheck;
  return (
    <li
      className={`home-task ${task.done ? "done" : ""} ${rejected ? "blocked" : ""}`}
      role="button"
      tabIndex={0}
      aria-label={`打开任务：${task.title}`}
      onClick={() => onOpen?.(task)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen?.(task);
        }
      }}
    >
      <button
        type="button"
        className="home-task-check"
        onClick={(event) => { event.stopPropagation(); onToggle(task); }}
        disabled={disabled}
        aria-label={task.done ? "标记未完成" : "标记完成"}
      >
        {busy ? <Loader2 size={14} className="spin" /> : task.done ? "✓" : ""}
      </button>
      <div className="home-task-body">
        <strong>{task.title}{task.critical && <span className="home-task-critical">重点</span>}</strong>
        <span className="home-task-meta">
          {(task.tags || []).slice(0, 3).map((tag) => <i key={tag}>{tag}</i>)}
          <i className={`home-task-type ${task.task_type || "review"}`}>{TYPE_LABELS[task.task_type] || "复习"}</i>
          {task.reason && <em>{task.reason}</em>}
          {rejected && <em className="home-task-warning"><CircleAlert size={12} /> 需先完成关联训练</em>}
        </span>
      </div>
      {actionable && (
        <button type="button" className="home-task-go" onClick={(event) => { event.stopPropagation(); onStart(task); }} disabled={disabled}>
          <Icon size={14} /> {task.primary_action?.label || "开始任务"}
        </button>
      )}
    </li>
  );
}
