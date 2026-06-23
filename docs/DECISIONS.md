# Decisions

更新时间：2026-06-23

## 已冻结决策

### D1. MVP 不直接实盘

MVP 默认只做 Backtest + Paper Trading。Live Trading 必须等回测、Paper、Stop Order Guard、Liquidation Guard、测试网和小资金配置全部通过后再开启。

### D2. 分层策略系统是新的策略主线

下一阶段策略主线从 `TREND_PULLBACK` / `REVERSAL_PROBE` 升级为独立的分层策略系统。策略系统以日线为主趋势、4h 为子趋势、1h 为确认、15m 为入场触发，并输出明确的 `strategy_type`。

必须支持的策略名：

- `SHORT_DAY_CORE`
- `SHORT_4H_1H_ADDON`
- `LONG_4H_HEDGE`
- `LONG_DAY_CORE`
- `LONG_4H_1H_ADDON`
- `SHORT_4H_HEDGE`

旧 `TREND_PULLBACK` / `REVERSAL_PROBE` 只保留历史兼容语义，不再作为新增策略系统的核心命名。

### D3. 趋势转换风险上限分级

- 早期试仓：单笔最大风险 0.2% 账户权益，仓位上限为主策略标准仓位的 20%。
- 确认试仓：单笔最大风险 0.3% 账户权益，仓位上限为主策略标准仓位的 30% - 50%。
- 最终仓位取 `风险上限仓位` 与 `评分仓位上限` 的较小值。

### D4. ADX 必须结合 DI 方向

ADX 只表示趋势强度，不表示趋势方向。趋势判断必须使用：

- 多头：`ADX >= min_adx AND DI_PLUS > DI_MINUS`
- 空头：`ADX >= min_adx AND DI_MINUS > DI_PLUS`

### D5. 日线主趋势不阻断 4h hedge

当日线为空头时，4h/1h 转多不代表必须平掉日线空头主仓；系统应允许 `LONG_4H_HEDGE` 与 `SHORT_DAY_CORE` 共存。当日线为多头时，对称允许 `SHORT_4H_HEDGE` 与 `LONG_DAY_CORE` 共存。

### D6. 回测、Paper 和未来 Live 共享策略系统与多周期对齐

策略系统只能使用最近已收盘的 1d、4h、1h、15m K 线。禁止使用正在形成中的高周期 K 线。

Backtest、Paper、Web 状态页和未来 Live 执行都必须调用同一套策略系统。其他模块不能复制策略条件，只能消费策略系统输出的 `StrategyDecision` / `StrategySignal` / diagnostics。

### D7. Paper/Backtest 先支持策略子仓，Live HEDGE 单独门槛

Paper 和 Backtest 必须从单仓位模型升级为策略子仓模型，至少支持同一 symbol 下主趋势 core 仓与反向 hedge 仓共存。

Live 仍默认关闭。未来真实下单若要支持同一 symbol 多空共存，必须使用 Binance Futures HEDGE position mode，并通过独立自检、API 权限、小资金配置和用户确认。

```yaml
paper_backtest:
  position_model: STRATEGY_BUCKETS
  allow_long_and_short_same_symbol: true
  margin_type: ISOLATED
live:
  default_enabled: false
  required_position_mode_for_hedge: HEDGE
```

### D8. AI 默认关闭

MVP 阶段 AI 过滤器默认关闭，只保留接口、日志和 deterministic stub。AI fallback 统一为 `BLOCK`。

### D9. Stop Order Guard 是实盘前硬门槛

真实持仓必须持续检查有效止损单。缺失止损时立即补挂，补挂失败时市价平仓并触发 CRITICAL 告警。

### D10. Liquidation Guard 是实盘前硬门槛

下单前必须检查止损价与强平价至少保持 1% 价格距离。不满足则禁止开仓。

### D11. Decimal 与 UTC

所有交易计算使用 Decimal。数据库时间统一 UTC，禁止依赖本地隐式时区。

### D12. 当前阶段只跑真实行情驱动的 Paper Trading

当前没有 Binance API Key，不接入测试网或真实下单 API。系统下一阶段以真实行情 WebSocket / REST 数据驱动 Paper Trading，先验证策略、风控、状态机和连续运行稳定性。

真实自动交易接入必须等待：

- Paper Trading 连续运行稳定。
- 策略表现和风控演练通过。
- 用户提供 Binance Futures Testnet 或生产 API Key。
- Live 启动前自检、小资金配置、Stop Order Guard、Liquidation Guard 仍全部通过。

### D13. 系统简单优先

后续开发必须优先保持系统简单，不为“架构完整”提前增加复杂度。

默认取舍：

- 能用一个清晰模块完成的，不拆成多层服务。
- 能用现有 Paper 状态文件和 CLI 验证的，不急着引入复杂任务调度、消息队列或状态平台。
- 能通过少量表完成复盘的，不提前设计大型数据仓库。
- 能用 deterministic 规则验证策略的，不提前接入 LLM 或外部复杂依赖。
- 新增抽象必须服务于真实痛点：减少重复、降低风险、改善可观察性或提升复盘能力。
- 每次新增能力都必须能说清楚“它解决了当前哪个实际问题”。
