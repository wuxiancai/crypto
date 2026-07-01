# Independent Timeline Strategy Design

## Goal

将当前 `WEEKLY_DAILY_H4_V1` 从“周线环境统领日线/4H”的耦合策略，改为三条独立时间线策略：

- `WEEKLY` 只由周线策略决定。
- `DAILY` 只由日线策略决定。
- `H4` 只由 4H 策略决定。

Paper、Backtest、Web 状态页和复盘必须按同一口径执行。

## Scope

本次改造只覆盖第一版 Paper / Backtest / Web 状态页，不开发 Live、测试网或真实下单。

本次必须新增并维护根目录 `trade_policy.md`，作为三条时间线交易政策的业务源文档。

## Required Behavior

### Position Model

同一交易对可以同时持有不同时间线的反向仓，例如：

- BTCUSDT `WEEKLY LONG`
- BTCUSDT `DAILY SHORT`
- BTCUSDT `H4 LONG`

同一交易对的同一时间线只能有一种方向：

- 已有 `WEEKLY LONG` 时，拒绝 `WEEKLY SHORT`。
- 已有 `DAILY SHORT` 时，拒绝 `DAILY LONG`。
- 已有 `H4 LONG` 时，拒绝 `H4 SHORT`。

同一时间线同一方向允许追加仓位：

- 已有 `DAILY SHORT` 时，再次出现 `DAILY SHORT` 有效信号可以追加。
- 追加仓位仍受账户级总风险、总名义价值、Liquidation Guard、Stop Order Guard 和费用过滤限制。

### Strategy Independence

各时间线只用自己的时间线生成交易信号：

- 周线开仓、减仓、退出只由周线 frame 决定。
- 日线开仓、止损、止盈、退出只由日线 frame 决定。
- 4H 开仓、止损、止盈、退出只由 4H frame 决定。

上级方向只用于分类和风险预算，不用于阻断下级交易：

- 日线参考周线方向，将日线信号分类为主方向、反弹或中性。
- 4H 参考日线方向，将 4H 信号分类为主方向、反弹或中性。

### Risk Budget Language

文档和 UI 不能把“风险预算高”写成“风险高”。

统一表述：

- 顺上级方向：结构风险较低，风险预算较高。
- 逆上级方向：结构风险较高，风险预算较低。

## Architecture

### Strategy Layer

`app/strategy/weekly_daily_h4_strategy.py` 保留为当前内核入口，但内部要拆成三条时间线评估函数：

- `evaluate_weekly_strategy()`
- `evaluate_daily_strategy()`
- `evaluate_h4_strategy()`

每个函数只负责自己的时间线。主入口按当前 K 线事件周期选择对应时间线评估，避免在 4H 事件上重复计算日线或周线交易动作。

### Adapter Layer

`app/paper/strategy_adapter.py` 继续负责从 `MultiTimeframeFrame` 构造 `TrendFrame`，但需要明确：

- 周线策略只消费 weekly frame。
- 日线策略消费 daily frame，并读取 weekly frame 方向作为分类参考。
- 4H 策略消费 h4 frame，并读取 daily frame 方向作为分类参考。

### Trading Layer

`app/paper/trading.py` 需要把冲突判断从“同一 level 任何仓位都冲突”改成：

- 同 symbol + 同 position_level + 反方向 = 冲突。
- 同 symbol + 同 position_level + 同方向 = 允许追加。
- 不同 position_level 不冲突。
- 不同策略内核仍按现有规则隔离。

追加仓位采用新增独立 `PaperPosition`，不在本次合并为均价仓。这样保留每次开仓的独立止损、止盈、费用、复盘记录，改动更小，也更符合可追溯原则。

### Backtest Layer

`app/paper/strategy_backtest.py` 和相关批量脚本必须复用同一策略信号函数和同一交易层冲突规则。回测事件仍按已收盘 K 线事件驱动；不同时间线只在自己的事件上执行。

### Web / Replay

Web 状态页和复盘事件需要展示：

- 时间线：`WEEKLY / DAILY / H4`。
- 方向：`LONG / SHORT`。
- 交易属性：主方向 / 反弹 / 中性。
- 风险预算来源：主方向预算 / 反弹预算 / 中性预算。
- 止损止盈依据：周线 / 日线 / 4H。

## Testing Strategy

新增或调整测试覆盖：

- 周线信号不再依赖日线确认。
- 日线信号不被周线方向阻断，但会按周线方向分类并调整风险预算。
- 4H 信号不被日线方向阻断，但会按日线方向分类并调整风险预算。
- 同一时间线反向仓被拒绝。
- 同一时间线同方向追加仓位被允许。
- 不同时间线反向仓可共存。
- Paper 与 Backtest 都执行同一规则。
- `trade_policy.md` 存在并包含三条时间线的触发、止损、止盈和退出政策。

## Non-Goals

- 不开发 Live。
- 不引入新交易所。
- 不引入多币种扫描。
- 不把追加仓位合并成均价仓。
- 不恢复旧 `LAYERED_DAILY_V1` 或旧 bucket 语义。
