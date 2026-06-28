# Ubuntu 一键部署

本项目当前只部署真实行情驱动的模拟交易，不部署真实下单。

## 一键部署

在 Ubuntu 服务器项目目录执行：

```bash
bash scripts/deploy_ubuntu.sh
```

脚本会执行：

- 如果 `.env` 不存在，自动执行 `cp .env.example .env`。
- 安装 `python3`、`python3-venv`。
- 检查 Docker：如果服务器已安装 Docker 则直接复用；如果存在 Docker CE 软件源则安装 `docker-ce`；否则回退安装 Ubuntu 自带 `docker.io`。
- 检查 Docker Compose：优先使用 `docker compose` plugin，必要时依次回退到 `docker-compose-v2` 和 `docker-compose`。
- 检测是否已有旧部署；如发现旧端口配置、Paper 状态或 PostgreSQL Docker volume，会询问保留数据库继续部署，还是删除数据库重新部署。
- 自动检测端口冲突。
- 生成 `.env.ports.generated`。
- 启动 PostgreSQL。
- 创建 `.venv` 并安装项目依赖。
- 执行 Alembic migration。
- 安装并启动 `crypto-paper.service` systemd 服务。
- 由 systemd 托管真实行情 Paper Trading 和中文 Web 状态页。
- 部署结束时打印 Web 页面地址、Web 端口、PostgreSQL 端口、端口配置文件、`.env` 配置说明和常用运维命令。

部署完成后，即使关闭 SSH 终端，服务也会继续运行；服务器重启后也会自动启动。

## 部署完成后看哪里

`deploy_ubuntu.sh` 结束时会打印类似：

```text
Web 页面地址:
  http://服务器IP:8765

端口信息:
  Web 页面端口: 8765
  PostgreSQL 端口: 55432
  端口配置文件: /path/to/crypto/.env.ports.generated
```

如果脚本自动识别到的是云服务器内网 IP，请用云厂商控制台里的公网 IP 替换：

```text
http://<云服务器公网IP>:Web页面端口
```

还需要确认云厂商安全组已放行 Web 页面端口。若服务器启用了 `ufw`，执行：

```bash
sudo ufw allow 8765/tcp
```

实际端口如果不是 `8765`，请以部署输出或 `.env.ports.generated` 里的 `PAPER_WEB_PORT` 为准。

如果浏览器打不开页面，先不要改 `.env`，按下面顺序确认：

```bash
cat .env.ports.generated
sudo systemctl status crypto-paper.service --no-pager
sudo journalctl -u crypto-paper.service -n 100 --no-pager
sudo ss -lntp | grep <PAPER_WEB_PORT>
curl -I http://127.0.0.1:<PAPER_WEB_PORT>/
sudo ufw status
```

判断方式：

- `cat .env.ports.generated`：确认真实 Web 端口，云服务器访问地址应使用 `PAPER_WEB_PORT`。
- `systemctl status` / `journalctl`：确认服务是否已启动、是否因为依赖或配置报错退出。
- `ss`：确认状态页进程是否真的监听了该端口。
- `curl 127.0.0.1`：如果本机能访问但公网不能访问，通常是云厂商安全组或 `ufw` 未放行。
- 云厂商控制台安全组必须放行 TCP `PAPER_WEB_PORT`，只在服务器里执行 `ufw allow` 不一定够。

## .env 需要配置什么

首次部署时脚本会自动创建 `.env`，等价于：

```bash
cp .env.example .env
```

第一版只运行 Paper Trading，不需要配置 Binance API Key，也不要配置真实下单参数。

通常只需要关注：

```bash
ENVIRONMENT=paper
EXECUTION_MODE=paper
BINANCE_BASE_URL=https://fapi.binance.com
```

如果服务器访问 Binance 主网 REST 受限，可以把 `.env` 中的 `BINANCE_BASE_URL` 改成当前服务器可访问的 Binance USDⓈ-M Futures endpoint。实际运行端口、PostgreSQL 密码和 `DATABASE_URL` 由 `.env.ports.generated` 自动生成，通常不需要手动改 `.env` 里的 `DATABASE_URL`。

截图里 `.env` 的 `POSTGRES_PASSWORD=change-me-to-a-strong-password` 是模板值；正常一键部署时，启动脚本会生成 `.env.ports.generated` 并在运行时覆盖数据库连接配置。因此页面打不开时，优先排查服务、监听端口和安全组，不要先改 `.env`。

## 重新部署时保留或删除数据库

再次执行：

```bash
bash scripts/deploy_ubuntu.sh
```

如果脚本检测到当前服务器可能已经部署过本项目，例如存在 `.env.ports.generated`、`runtime/paper-state.json` 或本项目 PostgreSQL Docker volume，会提示：

```text
请选择数据库处理方式：
  1) 保留数据库并继续部署（推荐）
  2) 删除数据库和本地 Paper 状态后重新部署
```

默认选择 `1`，会保留已有数据库和 Paper 状态，只更新代码、依赖、migration 和 systemd 服务。

选择 `2` 会停止旧服务，执行 Compose `down -v`，删除本项目 PostgreSQL volume，并删除 `runtime/paper-state.json`。这会清空本机数据库里的 Paper 复盘、回测归档和相关运行数据；只有确认要全新初始化时才选择。

非交互部署可以显式指定：

```bash
DEPLOY_DATABASE_MODE=keep bash scripts/deploy_ubuntu.sh
DEPLOY_DATABASE_MODE=reset bash scripts/deploy_ubuntu.sh
```

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

状态页里的批量参数回测动作默认禁用，避免公网请求触发重计算或清空回测归档。局域网临时研究确实需要使用批量页时，手动启动：

```bash
bash scripts/start.sh --ENABLE_BACKTEST
```

启动摘要中看到 `批量回测 Web 功能: 已启用` 后，再打开状态页使用批量回测。systemd 常驻服务不建议开启该功能。

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
- 当前用户没有 Docker 权限时，启动脚本会先验证 Docker daemon 访问权限，再自动尝试 `sudo docker compose`。

## Docker 权限不足

如果手动执行 `bash scripts/start.sh` 或 `docker ps` 报：

```text
permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock
```

说明当前用户还没有访问 Docker daemon 的权限。拉取新版脚本后，优先继续使用普通用户启动，脚本会只对 Docker 命令自动尝试 sudo：

```bash
bash scripts/start.sh
```

如果尚未拉取新版脚本、必须临时应急恢复运行，才使用：

```bash
sudo bash scripts/start.sh
```

长期修复建议把当前登录用户加入 `docker` 组，然后重新登录 SSH：

```bash
sudo usermod -aG docker $(whoami)
exit
```

重新登录后验证：

```bash
docker ps
bash scripts/start.sh
```

如果仍然失败，确认 Docker 服务已启动：

```bash
sudo systemctl enable --now docker
sudo systemctl status docker --no-pager
```

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
