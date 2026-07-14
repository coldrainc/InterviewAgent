function readFileBase64(filePath) {
  const fs = wx.getFileSystemManager();
  return new Promise((resolve, reject) => {
    fs.readFile({
      filePath,
      encoding: "base64",
      success(result) {
        resolve(result.data);
      },
      fail(error) {
        reject(new Error(error.errMsg || "读取文件失败"));
      }
    });
  });
}

function chooseResumeFile() {
  return new Promise((resolve, reject) => {
    wx.chooseMessageFile({
      count: 1,
      type: "file",
      extension: ["pdf", "md", "markdown"],
      success(result) {
        const file = result.tempFiles && result.tempFiles[0];
        if (!file) {
          reject(new Error("未选择文件"));
          return;
        }
        resolve(file);
      },
      fail(error) {
        reject(new Error(error.errMsg || "选择文件失败"));
      }
    });
  });
}

module.exports = {
  readFileBase64,
  chooseResumeFile
};
