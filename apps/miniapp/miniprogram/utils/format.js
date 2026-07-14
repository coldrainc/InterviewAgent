function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  const pad = (num) => String(num).padStart(2, "0");
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function normalizeError(error) {
  return error && error.message ? error.message : "操作失败，请稍后重试";
}

module.exports = {
  formatDateTime,
  normalizeError
};
