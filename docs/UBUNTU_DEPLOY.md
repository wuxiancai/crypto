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
- 检查 Docker Compose：优先使用 `docker compose` plugin，必要时依次回退到 `docker-compose-v2` 和 `docker-compose`。
- 自动检测端口冲突。
- 生成 `.env.ports.generated`。
- 启动 PostgreSQL。
- 创建 `.venv` 并安装项目依赖。
- 执行 Alembic migration。
- 安装并启动 `crypto-paper.service` systemd 服务。
- 由 systemd 托管真实行情 Paper Trading 和中文 Web 状态页。

部署完成后，即使关闭 SSH 终端，服务也会继续运行；服务器重启后也会自动启动。

## 端口顺延机制

默认端口：

- PostgreSQL：`55432`
- Web 状态页：`8765`

如果端口被占用，脚本会自动顺延：

- `55432` 被占用则尝试 `55433`、`55434` ...
- `8765` 被占用则尝试 `8766`、`8767` ...

端口检测同时覆盖：

- 宿主机已有进程监听的端口，例如服务器已有 PostgreSQL。
- Docker 已发布的宿主机端口，例如其他服务的 Postgres 容器。

最终端口写入：

```bash
.env.ports.generated
```

查看端口：

```bash
cat .env.ports.generated
```

## 已有 PostgreSQL 服务

服务器上已经运行其他 PostgreSQL 服务时，不需要停止原服务。部署脚本会跳过已占用的宿主机端口，并为本项目的 PostgreSQL 自动选择下一个可用端口。

本项目不再固定 Postgres 容器名，避免和旧部署或其他 Compose 项目的容器名冲突。

## PostgreSQL 资源限制

个人 2c2g 云服务器部署时，PostgreSQL 必须限制内存和连接数，避免与同机其他项目共同运行时抢占自动交易进程资源。

当前 `docker-compose.yml` 已为 PostgreSQL 设置保守启动参数：`shared_buffers=128MB`、`work_mem=4MB`、`maintenance_work_mem=64MB`、`max_connections=30`，并限制容器内存为 `512m`。云服务器只运行自动交易所需进程，不在服务器上执行批量回测、参数网格搜索、开发测试或其他重计算任务。

状态页里的批量参数回测动作默认禁用，避免公网请求触发重计算或清空回测归档。本机临时研究确实需要使用批量页时，手动设置：

```bash
PAPER_ENABLE_BATCH_BACKTEST=1 bash scripts/run_paper_status_web.py
```

systemd 部署不建议开启该变量。

如果服务器上残留早期版本创建的固定名容器，可以先查看：

```bash
docker ps -a --filter name=crypto_quant_postgres
```

确认不是正在使用的数据后再清理：

```bash
docker rm crypto_quant_postgres
```

## 再次启动

部署后服务由 systemd 托管。常用命令：

```bash
sudo systemctl status crypto-paper.service --no-pager
sudo systemctl restart crypto-paper.service
sudo systemctl stop crypto-paper.service
sudo journalctl -u crypto-paper.service -f
```

如果依赖已经装好，但当前服务器没有 systemd，才使用手动启动：

```bash
bash scripts/start.sh
```

再次启动默认复用 `.env.ports.generated` 中的端口，不会重新顺延端口。因此部署后第一次输出的 Web 页面端口会保持稳定。

如果确实需要重新分配端口，可以执行：

```bash
REGENERATE_PORTS=1 bash scripts/start.sh
```

或者删除 `.env.ports.generated` 后重新启动。

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
- 安装 Ubuntu `docker.io` 时不再把 `docker-compose-plugin` 绑在同一个 apt 命令里，避免默认源缺少该包时让 Docker Engine 安装也失败。
- Docker Compose 会单独探测安装，依次尝试 `docker-compose-plugin`、`docker-compose-v2`、`docker-compose`。
- 当前用户没有 Docker 权限时，启动脚本会尝试使用 `sudo docker compose`。

如果部署时报：

```text
E: Unable to locate package docker-compose-plugin
```

请先拉取最新代码后重新执行：

```bash
bash scripts/deploy_ubuntu.sh
```

新版脚本会自动回退到当前 Ubuntu 镜像可用的 Compose 包名。

## Python Editable 安装失败

如果部署时出现：

```text
error: Multiple top-level packages discovered in a flat-layout
Getting requirements to build editable did not run successfully
```

通常是 setuptools 自动包发现把 `runtime/`、`migrations/` 等目录误判为顶层包。当前项目已在 `pyproject.toml` 固定包发现规则：

- 只打包 `app*`。
- 排除 `runtime*`、`migrations*`、`tests*`。

验证命令：

```bash
.venv/bin/python -m pip install -e .
```

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

应用日志目录：

```bash
runtime/logs
```

常用查看命令：

```bash
tail -f runtime/logs/paper-realtime.log
tail -f runtime/logs/paper-status-web.log
```

systemd 服务日志：

```bash
sudo journalctl -u crypto-paper.service -f
```

## 停止服务

统一停止入口：

```bash
bash scripts/stop.sh
```

该脚本会先尝试停止 `crypto-paper.service`，再兜底停止 Paper 实时交易进程、Web 状态页进程和 PostgreSQL 容器。

如只想停止 Paper/Web，保留 PostgreSQL 容器运行：

```bash
STOP_POSTGRES=0 bash scripts/stop.sh
```
