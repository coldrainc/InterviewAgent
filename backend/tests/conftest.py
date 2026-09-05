"""pytest 全局配置。

测试进程内所有 TestClient 请求共享同一个固定窗口限流器（按 client host 计数），
全量套件的请求总量会超过默认 60/分钟阈值导致 429 污染，这里在测试环境放宽限流。
"""

import os

os.environ.setdefault("INTERVIEW_RATE_LIMIT_PER_MINUTE", "100000")
