import { useEffect, useState } from "react";
import { AlertTriangle, CalendarClock, Download, RotateCcw, Trash2 } from "lucide-react";
import { productErrorMessage } from "../../utils/productSafety";

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

function errorMessage(error, fallback) {
  return productErrorMessage(error, fallback);
}

function downloadJson(payload) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `interview-agent-data-${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function PrivacyDataPanel({ client, accountKey }) {
  const [deletion, setDeletion] = useState(null);
  const [confirmation, setConfirmation] = useState("");
  const [reason, setReason] = useState("");
  const [status, setStatus] = useState("loading");
  const [message, setMessage] = useState("");

  async function loadDeletion() {
    setStatus("loading");
    setMessage("");
    try {
      const result = await client.privacy.getDeletion();
      setDeletion(result?.request || null);
      setStatus("idle");
    } catch (error) {
      setStatus("error");
      setMessage(errorMessage(error, "无法读取删除申请，请稍后重试。"));
    }
  }

  useEffect(() => {
    loadDeletion();
  }, [accountKey]);

  async function exportData() {
    setStatus("exporting");
    setMessage("");
    try {
      downloadJson(await client.privacy.exportData());
      setStatus("idle");
      setMessage("数据副本已导出。文件不包含密码、登录信息和支付凭据。 ");
    } catch (error) {
      setStatus("error");
      setMessage(errorMessage(error, "数据导出失败，请稍后重试。"));
    }
  }

  async function scheduleDeletion() {
    if (confirmation !== "DELETE") return;
    setStatus("deleting");
    setMessage("");
    try {
      const result = await client.privacy.scheduleDeletion(reason.trim());
      setDeletion(result);
      setConfirmation("");
      setReason("");
      setStatus("idle");
      setMessage("删除申请已提交。冷静期内可以随时取消。 ");
    } catch (error) {
      setStatus("error");
      setMessage(errorMessage(error, "删除申请提交失败，请稍后重试。"));
    }
  }

  async function cancelDeletion() {
    setStatus("cancelling");
    setMessage("");
    try {
      await client.privacy.cancelDeletion();
      setDeletion(null);
      setStatus("idle");
      setMessage("删除申请已取消，账户和产品数据将继续保留。 ");
    } catch (error) {
      setStatus("error");
      setMessage(errorMessage(error, "取消失败，请刷新后重试。"));
    }
  }

  const busy = ["loading", "exporting", "deleting", "cancelling"].includes(status);

  return (
    <section className="account-block wide privacy-data-panel">
      <div className="panel-heading">
        <span>隐私与数据</span>
        <button type="button" className="secondary-action inline compact" onClick={loadDeletion} disabled={busy} title="刷新删除申请">
          <RotateCcw size={15} />
          刷新
        </button>
      </div>

      <div className="privacy-action-row">
        <div>
          <strong>导出我的数据</strong>
          <p>下载账户、面试、题库、学习计划、打卡和训练记录副本。</p>
        </div>
        <button type="button" className="secondary-action inline" onClick={exportData} disabled={busy}>
          <Download size={16} />
          {status === "exporting" ? "正在导出" : "导出数据"}
        </button>
      </div>

      <div className="privacy-divider" />

      {deletion?.status === "scheduled" ? (
        <div className="privacy-deletion-state">
          <div className="privacy-warning-heading">
            <CalendarClock size={18} />
            <div>
              <strong>账户删除已排期</strong>
              <p>预计执行时间：{formatDate(deletion.execute_after)}</p>
            </div>
          </div>
          <p>执行后将删除简历、面试、题库、学习计划和训练数据，并退出所有设备。账务流水和必要安全记录仅按合规要求保留。</p>
          <button type="button" className="secondary-action inline" onClick={cancelDeletion} disabled={busy}>
            <RotateCcw size={16} />
            {status === "cancelling" ? "正在取消" : "取消删除"}
          </button>
        </div>
      ) : (
        <div className="privacy-delete-form">
          <div className="privacy-warning-heading">
            <AlertTriangle size={18} />
            <div>
              <strong>删除账户和产品数据</strong>
              <p>申请后有 7 天冷静期；到期执行前仍可取消。</p>
            </div>
          </div>
          <label>
            <span>删除原因（选填）</span>
            <textarea value={reason} maxLength={2000} rows={3} onChange={(event) => setReason(event.target.value)} placeholder="帮助我们改进产品" />
          </label>
          <label>
            <span>输入 DELETE 确认</span>
            <input value={confirmation} autoComplete="off" onChange={(event) => setConfirmation(event.target.value)} placeholder="DELETE" />
          </label>
          <button type="button" className="danger-inline large privacy-delete-button" onClick={scheduleDeletion} disabled={busy || confirmation !== "DELETE"}>
            <Trash2 size={16} />
            {status === "deleting" ? "正在提交" : "申请删除账户"}
          </button>
        </div>
      )}

      {status === "loading" && <p className="privacy-status">正在读取隐私设置...</p>}
      {message && <p className={`privacy-status ${status === "error" ? "error" : "success"}`} role="status">{message}</p>}
    </section>
  );
}
