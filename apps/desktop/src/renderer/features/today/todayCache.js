const CACHE_SCHEMA_VERSION = 1;
const CACHE_PREFIX = "interview-agent:today:";

function storageKey(account) {
  if (!account?.tenant_id || !account?.user_id) return "";
  return `${CACHE_PREFIX}${account.tenant_id}:${account.user_id}`;
}

export function loadTodayCache(account) {
  const key = storageKey(account);
  if (!key) return null;
  try {
    const cached = JSON.parse(window.localStorage.getItem(key) || "null");
    if (cached?.schema_version !== CACHE_SCHEMA_VERSION || !cached?.data) return null;
    return cached;
  } catch (_error) {
    return null;
  }
}

export function saveTodayCache(account, data) {
  const key = storageKey(account);
  if (!key || !data) return;
  try {
    window.localStorage.setItem(key, JSON.stringify({
      schema_version: CACHE_SCHEMA_VERSION,
      cached_at: new Date().toISOString(),
      data
    }));
  } catch (_error) {
    // Cache failure must not block the live dashboard.
  }
}
