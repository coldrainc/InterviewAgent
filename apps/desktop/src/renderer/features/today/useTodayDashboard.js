import { useCallback, useEffect, useState } from "react";
import { getInterviewAgentClient } from "../../apiClient";
import { loadTodayCache, saveTodayCache } from "./todayCache";
import { productErrorMessage } from "../../utils/productSafety";

const api = getInterviewAgentClient();

export function useTodayDashboard(account) {
  const [state, setState] = useState({ status: "idle", data: null, error: "" });

  const reload = useCallback(async () => {
    if (!account) {
      setState({ status: "idle", data: null, error: "" });
      return;
    }
    setState((current) => ({ ...current, status: "loading", error: "" }));
    try {
      const data = await api.learning.today();
      saveTodayCache(account, data);
      setState({ status: "ready", data, error: "", cachedAt: "" });
    } catch (error) {
      const cached = loadTodayCache(account);
      if (cached) {
        setState({
          status: "offline",
          data: cached.data,
          cachedAt: cached.cached_at,
          error: productErrorMessage(error, "当前无法连接服务。")
        });
      } else {
        setState({ status: "error", data: null, error: productErrorMessage(error, "今日工作台加载失败，请稍后重试。") });
      }
    }
  }, [account]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { ...state, reload };
}
