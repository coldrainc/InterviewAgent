# Interview Agent 单服务器部署手册

## 1. 交付形态

一台服务器运行以下容器：

| 服务 | 作用 | 外部暴露 |
| --- | --- | --- |
| `web` | Nginx 托管 React Web，并同源代理 `/api` | `APP_PORT`，默认 `8080` |
| `api` | FastAPI、Agent Harness、后台隐私删除任务 | 仅 `127.0.0.1:8020` |
| `postgres` | 用户、会话、题库、计划、打卡、计费主库 | 不暴露 |
| `minio` | 简历和资料原文件 | 不暴露 |
| `qdrant` | RAG 向量索引 | 不暴露 |
| `embedding` | 本地 embedding 模型 | 不暴露 |

代码和数据严格分离。更新源码或重建容器不会删除以下 Docker 卷：

- `postgres_data`
- `minio_data`
- `qdrant_storage`
- `interview_agent_runtime`
- `interview_agent_model_cache`

## 2. 服务器要求

- Linux x86_64 或 arm64
- Docker Engine 24+
- Docker Compose v2
- 建议至少 4 核、8 GB 内存、30 GB 可用磁盘
- 域名部署需要现有 Nginx 和 Let's Encrypt 证书
- 服务器能够访问所选模型 API；首次启动 embedding 时需要下载模型

如果服务器无法访问 Docker Hub，可在 `.env.production` 中把 `PYTHON_IMAGE`、`NODE_IMAGE`、`NGINX_IMAGE`、`POSTGRES_IMAGE`、`MINIO_IMAGE`、`QDRANT_IMAGE` 和 `BACKUP_HELPER_IMAGE` 改为可访问的镜像仓库地址，无需修改源码。已验证 MinIO 可使用 `quay.io/minio/minio:RELEASE.2024-07-16T23-46-41Z`，Qdrant 可使用 `m.daocloud.io/docker.io/qdrant/qdrant:v1.11.5`。

不要将 PostgreSQL、MinIO 或 Qdrant 端口开放到公网。Compose 默认只公开 Web 端口，API 也只绑定回环地址。

## 3. 首次部署

```bash
git clone https://github.com/coldrainc/InterviewAgent.git
cd InterviewAgent
PUBLIC_URL=https://example.com ./deploy/stack.sh init
vim .env.production
./deploy/stack.sh deploy
```

在 `.env.production` 至少填写一个模型密钥，例如：

```dotenv
DEEPSEEK_API_KEY=your-key
```

`init` 会生成数据库、MinIO、登录 Token 和支付回调随机密钥，文件权限为 `600`。不要提交该文件。

如果暂时没有域名：

```bash
PUBLIC_URL=http://服务器IP:8080 ./deploy/stack.sh init
./deploy/stack.sh deploy
```

防火墙只需要放行 `8080`；使用域名和宿主机 Nginx 时只放行 `80/443`。

## 4. 从旧版升级

在旧部署的同一个仓库目录执行：

```bash
git pull origin main
PUBLIC_URL=https://原域名 ./deploy/stack.sh init
vim .env.production
./deploy/stack.sh deploy
```

如果从曾将 `.interview_agent/memory` 纳入共享 RAG 的旧版本升级，部署成功后必须立即重建一次公共索引：

```bash
./deploy/stack.sh index
```

新版本禁止把简历、会话、回答、报告和历史 memory 写入共享索引；运行时也会过滤旧索引中的私有来源。重建用于从存储中彻底清除旧私有片段。

升级脚本会：

1. 识别旧版常见的 PostgreSQL、MinIO、Qdrant 卷名。
2. 对已存在的数据卷沿用旧版存储密码，避免挂载成功但认证失败。
3. 在旧服务仍可用时先完成新版镜像构建；镜像源异常不会提前中断线上版本。
4. 从停止旧服务开始启用失败恢复门禁；迁移或健康检查失败时，自动恢复本次发布前的数据卷快照、应用镜像和原有服务。
5. 停止旧 `interview-agent-api` systemd 服务和旧基础设施容器；新版健康检查通过后才禁用旧 systemd 服务，避免服务器重启后争抢端口。
6. 在 `backups/<时间>/` 生成冷备份。
7. 把旧 `.interview_agent` 会话导出、RAG metadata 和安全日志迁入持久化卷。
8. 运行当前 Alembic 全部迁移，再启动新版 API 和 Web。
9. 当服务器已有对应域名证书时，自动把原 Nginx 域名切换到新版容器。

旧版若使用了自定义数据库或 MinIO 密码，请确保旧 `.env` 仍在仓库根目录；初始化会从中继承。初始化后应再次核对 `.env.production` 的 `POSTGRES_PASSWORD`、`MINIO_ROOT_PASSWORD` 和卷名。

升级前不要执行 `docker compose down -v`，`-v` 会删除数据卷。

## 5. 日常发布

```bash
git pull origin main
./deploy/stack.sh deploy
```

已有数据库卷时，每次发布都会强制生成冷备份。这是数据库迁移失败后自动恢复旧版本的前提，发布入口不允许跳过。

关闭自动宿主机 Nginx 配置：

```bash
CONFIGURE_HOST_NGINX=0 ./deploy/stack.sh deploy
```

## 6. 状态与日志

```bash
./deploy/stack.sh status
./deploy/stack.sh logs api
./deploy/stack.sh logs web
./deploy/stack.sh logs embedding
./deploy/stack.sh doctor
```

健康检查：

```bash
curl -fsS http://127.0.0.1:8080/healthz
curl -fsS http://127.0.0.1:8080/api/health
```

## 7. 备份与恢复

手动备份：

```bash
./deploy/stack.sh backup
```

备份包含所有业务数据卷、运行时文件、配置快照和 Git revision；由当前 Compose 管理的 PostgreSQL 还会额外生成 SQL dump。备份过程会短暂停止写入，完成后自动恢复服务。

恢复会覆盖当前卷，必须显式确认：

```bash
RESTORE_CONFIRM=YES ./deploy/stack.sh restore backups/20260905-120000
```

恢复时当前 `.env.production` 中的数据库和 MinIO凭据必须与备份一致。需要跨服务器恢复时，一并安全传输备份中的 `env.production`，人工核对后放到项目根目录，权限设为 `600`。

建议再配置一份异机或对象存储备份，并定期执行实际恢复演练。服务器本地备份不能覆盖整机磁盘损坏场景。

## 8. RAG 索引

首次部署且运行时卷没有索引时会自动构建 BM25 基础索引，因此 embedding 模型下载失败不会阻塞核心网站上线。知识库变化后，手动构建完整向量索引：

```bash
./deploy/stack.sh index
```

首次下载 `BAAI/bge-small-zh-v1.5` 可能需要几分钟。模型缓存在独立卷中，后续发布不会重复下载。

## 9. 回滚边界

应用镜像可以通过切换 Git revision 后重新执行 `deploy` 回滚。数据库 migration 不保证所有 revision 都可无损降级，因此生产回滚的可靠路径是：

1. 停止服务。
2. 切回旧 Git revision。
3. 从发布前备份恢复数据卷。
4. 重新执行该 revision 的部署命令。

不要只降级代码而保留不可兼容的新数据库结构。
