# 从 ZIP 部署到单台服务器

发布 ZIP 是源码部署包，不包含 `node_modules`、Python 虚拟环境、构建缓存、数据库、上传文件、生产密钥或个人知识库。服务器只需要 `unzip`、Docker Engine 24+、Docker Compose v2、`curl` 和 `openssl`，Node.js 与 Python 依赖会在 Docker 镜像构建时自动安装。

## 首次部署

```bash
unzip InterviewAgent-server-*.zip
cd InterviewAgent-server-*
PUBLIC_URL=https://example.com ./deploy/stack.sh init
vim .env.production
./deploy/stack.sh deploy
```

没有域名时，把 `PUBLIC_URL` 改为 `http://服务器IP:8080`。在 `.env.production` 中至少配置一个模型服务密钥；生产密钥只保存在服务器，禁止放回 ZIP。

部署完成后验证：

```bash
./deploy/stack.sh status
curl -fsS http://127.0.0.1:8080/healthz
curl -fsS http://127.0.0.1:8080/api/health
```

## 升级已有部署

先在旧目录执行备份，再将旧生产配置安全复制到新目录：

```bash
cd /path/to/old/InterviewAgent
./deploy/stack.sh backup

cd /path/to/releases
unzip InterviewAgent-server-*.zip
cp /path/to/old/InterviewAgent/.env.production InterviewAgent-server-*/.env.production
chmod 600 InterviewAgent-server-*/.env.production
cd InterviewAgent-server-*
./deploy/stack.sh deploy
```

`deploy` 会复用 `.env.production` 中指定的 Docker 数据卷，执行发布前备份、数据库迁移和健康检查。不要执行 `docker compose down -v`，否则会删除业务数据卷。

## 生成发布包

```bash
make package-server
```

默认输出到项目同级的 `release-artifacts/`，同时生成 SHA-256 校验文件。可通过 `OUTPUT_DIR=/path make package-server` 指定输出目录。
