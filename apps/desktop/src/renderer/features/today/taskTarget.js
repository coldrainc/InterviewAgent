export function taskTarget(task) {
  const payload = task?.link_payload && typeof task.link_payload === "object" ? task.link_payload : {};
  if (task?.task_type === "interview") return { screen: "chat", payload };
  if (task?.task_type === "practice") return { screen: "practice", payload };
  return { screen: "review-site", payload };
}
