const api = require("../../utils/api");
const { config } = require("../../utils/config");
const { chooseResumeFile, readFileBase64 } = require("../../utils/file");
const { formatDateTime, normalizeError } = require("../../utils/format");

Page({
  data: {
    loading: false,
    resumes: [],
    selectedResumeId: "",
    error: ""
  },

  onLoad() {
    api.restoreToken();
    this.loadSelected();
    this.loadResumes();
  },

  onShow() {
    this.loadSelected();
    this.loadResumes();
  },

  loadSelected() {
    this.setData({
      selectedResumeId: wx.getStorageSync(config.storageKeys.selectedResumeId) || ""
    });
  },

  async loadResumes() {
    if (!ensureLogin("查看和管理历史简历前需要先登录。")) return;
    this.setData({ loading: true, error: "" });
    try {
      const resumes = await api.listResumes();
      this.setData({
        resumes: resumes.map((item) => ({
          ...item,
          createdLabel: formatDateTime(item.created_at),
          summaryShort: item.summary ? item.summary.slice(0, 90) : "暂无摘要"
        }))
      });
    } catch (error) {
      this.setData({ error: normalizeError(error) });
    } finally {
      this.setData({ loading: false });
    }
  },

  async uploadResume() {
    if (this.data.loading) return;
    if (!ensureLogin("上传和保存简历前需要先登录。")) return;
    this.setData({ loading: true, error: "" });
    try {
      const file = await chooseResumeFile();
      const contentBase64 = await readFileBase64(file.path);
      const stored = await api.importResume({
        filename: file.name,
        contentBase64,
        sourcePath: file.path
      });
      this.selectResumeRecord(stored);
      wx.showToast({ title: "简历已保存", icon: "success" });
      await this.loadResumes();
    } catch (error) {
      this.setData({ error: normalizeError(error) });
    } finally {
      this.setData({ loading: false });
    }
  },

  selectResume(event) {
    const resumeId = event.currentTarget.dataset.id;
    const resume = this.data.resumes.find((item) => item.id === resumeId);
    if (resume) {
      this.selectResumeRecord(resume);
      wx.showToast({ title: "已选择", icon: "success" });
    }
  },

  selectResumeRecord(resume) {
    wx.setStorageSync(config.storageKeys.selectedResumeId, resume.id);
    wx.setStorageSync(`${config.storageKeys.selectedResumeId}:name`, resume.filename);
    this.setData({ selectedResumeId: resume.id });
  },

  deleteResume(event) {
    if (!ensureLogin("删除简历前需要先登录。")) return;
    const resumeId = event.currentTarget.dataset.id;
    wx.showModal({
      title: "删除简历",
      content: "删除后该简历文件和解析记录都会移除，确认继续？",
      confirmColor: "#dc2626",
      success: async (result) => {
        if (!result.confirm) return;
        await this.confirmDelete(resumeId);
      }
    });
  },

  async confirmDelete(resumeId) {
    this.setData({ loading: true, error: "" });
    try {
      await api.deleteResume(resumeId);
      if (this.data.selectedResumeId === resumeId) {
        wx.removeStorageSync(config.storageKeys.selectedResumeId);
        wx.removeStorageSync(`${config.storageKeys.selectedResumeId}:name`);
        this.setData({ selectedResumeId: "" });
      }
      await this.loadResumes();
    } catch (error) {
      this.setData({ error: normalizeError(error) });
    } finally {
      this.setData({ loading: false });
    }
  }
});

function ensureLogin(content) {
  api.restoreToken();
  if (config.apiToken) return true;
  wx.showModal({
    title: "需要登录",
    content,
    confirmText: "去登录",
    success(result) {
      if (result.confirm) {
        wx.switchTab({ url: "/pages/profile/profile" });
      }
    }
  });
  return false;
}
