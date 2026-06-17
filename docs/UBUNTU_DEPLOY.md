# Ubuntu 一键部署

本项目当前只部署真实行情驱动的模拟交易，不部署真实下单。

## 一键部署

在 Ubuntu 服务器项目目录执行：

```bash
bash scripts/deploy_ubuntu.sh
```

脚本会执行：

- 安装 `python3`、`python3-venv`。
- 检查 Docker：如果服务器已安装 Docker 则直接复用；如果存在 Docker CE 软件源则安装 `docker-ce`；否则回退安装 Ubuntu 自带 `docker.io`。
- 检查 Docker Compose：优先使用 `docker compose` plugin，必要时回退到 `docker-compose`。
- 自动检测端口冲突。
- 生成 `.env.ports.generated`。
- 启动 PostgreSQL。
- 创建 `.venv` 并安装项目依赖。
- 执行 Alembic migration。
- 启动真实行情 Paper Trading。
- 启动中文 Web 状态页。

## 端口顺延机制

默认端口：

- PostgreSQL：`55432`
- Web 状态页：`8765`

如果端口被占用，脚本会自动顺延：

- `55432` 被占用则尝试 `55433`、`55434` ...
- `8765` 被占用则尝试 `8766`、`8767` ...

最终端口写入：

```bash
.env.ports.generated
```

查看端口：

```bash
cat .env.ports.generated
```

## 再次启动

如果依赖已经装好，只需要重新启动服务：

```bash
bash scripts/start_ubuntu.sh
```

## Docker 安装冲突

如果服务器之前安装过 Docker CE 或添加过 Docker CE 软件源，Ubuntu 的 `docker.io` 可能会与 `containerd.io` 冲突，典型错误是：

```text
containerd.io : Conflicts: containerd
E: Error, pkgProblemResolver::Resolve generated breaks
```

当前部署脚本已经处理该场景：

- 已有 `docker` 命令时不重新安装 Docker Engine。
- 可安装 `docker-ce` 时优先安装 Docker CE 相关包。
- 没有 Docker CE 候选包时才安装 Ubuntu `docker.io`。
- 当前用户没有 Docker 权限时，启动脚本会尝试使用 `sudo docker compose`。

## 查看页面

脚本结束时会输出：

```text
Web 页面地址: http://服务器IP:端口
```

页面显示：

- 账户权益。
- 持仓情况。
- 全部模拟交易记录。
- 买入价。
- 卖出价。
- 使用策略。
- 拒绝信号。

## 日志

日志目录：

```bash
runtime/logs
```

常用查看命令：

```bash
tail -f runtime/logs/paper-realtime.log
tail -f runtime/logs/paper-status-web.log
```

## 停止服务

停止模拟交易和 Web 页面：

```bash
pkill -f scripts/run_paper_realtime.py
pkill -f scripts/run_paper_status_web.py
```

停止 PostgreSQL：

```bash
docker compose --env-file .env.ports.generated down
```
