# pysc2-compat（smacnt）性能优化逐文件分析（第一版）

## 当前推进状态（2026-02-27）

### 已落地（Phase 0 - 评测基建第 1 步）

已升级 `pysc2/bin/benchmark_env_step.py`，新增以下能力：
- 可复现参数：`--seed`、`--agent_race`、`--bot_race`
- 评测稳定化参数：`--warmup_steps`、`--repeats`
- 结构化落盘：`--output_prefix` 或 `--output_dir`（自动输出 JSON + CSV）
- 聚合统计：自动输出 mean/median/min/max/std（多次运行）
- 环境元信息落盘：Python/Protobuf 版本与后端、pysc2 路径

### 最新版 vs 历史基线（smacnt，单次快速对照）

对照口径：
- 历史：`tests/profiles/profile_env_step_smacnt_raw.txt`
- 最新：`tests/profiles/profile_env_step_latest_smacnt_raw.txt`

关键指标：
- `Total Time`: `17.3919 s -> 18.1443 s`（`+4.33%`）
- `Average SPS`: `115.00 -> 110.23`（`-4.15%`）
- `Latency Mean`: `7.5485 ms -> 7.9390 ms`（`+5.17%`）
- `Latency P99`: `11.1290 ms -> 10.4352 ms`（`-6.23%`）

热点项变化（step_env 分解）：
- `step_env`: `15.0907 s -> 15.7947 s`（`+4.67%`）
- `step_env.observe.read.read_response`: `10.9385 s -> 11.3726 s`（`+3.97%`）
- `step_env.transform_obs`: `1.6201 s -> 1.6523 s`（`+1.99%`）

说明：
- 本次“最新版”用于验证评测链路可用，仍是单次 run，且使用随机对局流程；
- 后续应使用 `repeats>=3`（建议 5）+ 固定 race/seed，采用中位数作为主结论。

### 已落地（Phase 0 - 观测裁剪第 2 步）

在 `pysc2/lib/features.py` 与 `pysc2/bin/benchmark_env_step.py` 中落地了可选观测裁剪开关：
- `include_ui_data`（默认 `True`）
- `include_score_details`（默认 `True`，仅控制 `score_by_category/score_by_vital`）
- `include_last_actions`（默认 `True`）

说明：
- 为保持兼容，`score_cumulative` 保持始终输出（避免影响 score-based reward 逻辑）。
- 默认值均为 `True`，不改变现有用户行为；只在显式关闭时生效。

本轮对照数据（同参数，同 seed，`steps=2000, repeats=3`）：
- 默认配置输出：
  - `tests/profiles/profile_env_step_phase0_default_smacnt_raw.txt`
  - `tests/profiles/profile_env_step_phase0_default_smacnt.json`
  - `tests/profiles/profile_env_step_phase0_default_smacnt.csv`
- 轻量配置输出（`--obs_include_ui_data=false --obs_include_score_details=false --obs_include_last_actions=false`）：
  - `tests/profiles/profile_env_step_phase0_light_smacnt_raw.txt`
  - `tests/profiles/profile_env_step_phase0_light_smacnt.json`
  - `tests/profiles/profile_env_step_phase0_light_smacnt.csv`

聚合结果（light vs default）：
- `Total Time mean`: `17.2551 -> 17.1352 s`（`-0.70%`）
- `Total Time median`: `17.3664 -> 16.8307 s`（`-3.08%`）
- `SPS mean`: `116.08 -> 116.86`（`+0.67%`）
- `SPS median`: `115.16 -> 118.83`（`+3.18%`）
- `Latency Mean mean`: `7.8665 -> 7.8052 ms`（`-0.78%`）

热点项变化（按 run 平均）：
- `step_env.transform_obs`: `-5.92%`
- `step_env.transform_obs.score`: `-77.18%`
- `step_env.transform_obs.ui`: `-100.00%`
- `step_env.transform_obs.last_actions`: `-100.00%`

结论：
- “按需关闭非必要观测字段”在当前链路下已得到可测收益（约 `+0.7%` mean，`+3.2%` median）。
- 下一步应继续做 `sc2_env` 单智能体 fast-path，叠加收益。

### 已落地（Phase 0 - 单控制器 fast-path + feature layer 预分配）

本轮在 `pysc2/env/sc2_env.py` 与 `pysc2/lib/features.py` 继续推进：
- `sc2_env.py`：单控制器路径直调（`join_game/game_info/actions/act/step/observe`）
- `features.py`：`feature_screen/feature_minimap` 改为预分配数组并逐层填充（替换 `np.stack([...])` 临时列表）

对照口径（同参数、同 seed、`steps=2000, repeats=3`）：
- fast-path 基线：
  - `tests/profiles/profile_env_step_phase0_fastpath_default_smacnt.json`
  - `tests/profiles/profile_env_step_phase0_fastpath_light_smacnt.json`
- 叠加预分配后：
  - `tests/profiles/profile_env_step_phase0_prealloc_default_smacnt.json`
  - `tests/profiles/profile_env_step_phase0_prealloc_light_smacnt.json`

结果摘要：
- **default（prealloc vs fast-path 基线）**
  - `Total Time mean`: `-2.39%`
  - `SPS mean`: `+2.48%`
  - `Latency Mean mean`: `-2.77%`
  - `step_env.transform_obs`: `-7.52%`
  - `step_env.transform_obs.feature_screen`: `-24.76%`
- **light（prealloc vs fast-path 基线）**
  - `Total Time mean`: `-1.96%`
  - `SPS mean`: `+2.06%`
  - `Latency Mean mean`: `-2.21%`
  - `step_env.transform_obs`: `-15.71%`
  - `step_env.transform_obs.feature_screen`: `-32.38%`

与 Phase 0 第2步提交时的 default 基线相比：
- `Total Time mean`: `-0.58%`
- `SPS mean`: `+0.55%`
- `Latency Mean mean`: `-0.67%`
- `Latency P99 mean`: `+3.53%`（尾延迟仍有波动）

阶段结论：
- feature layer 预分配是有效优化点，且在 `transform_obs` 子项上有稳定收益。
- 单控制器 fast-path 的收益不够稳定，需继续用更长窗口（建议 `repeats=5~7`）确认其净效应。

### 已落地（Phase 0 - 单控制器 no-op 动作过滤）

在 `pysc2/env/sc2_env.py` 的单控制器路径中新增了 no-op 过滤：
- 将 `actions[0]` 中 `ListFields()==False` 的空动作剔除
- 对仅 1 个真实动作的情况走 `controller.act(...)`
- 对多真实动作走 `controller.actions(RequestAction(...))`

对照口径：
- 基线：`tests/profiles/profile_env_step_phase0_prealloc_default_smacnt.json`
- 过滤后：`tests/profiles/profile_env_step_phase0_noopfilter_default_smacnt.json`

结果（no-op filter vs prealloc default）：
- `Total Time mean`: `-1.97%`（`16.8167 vs 17.1554 s`）
- `SPS mean`: `+1.99%`（`119.03 vs 116.71`）
- `Latency Mean mean`: `-2.09%`
- `Latency P99 mean`: `-3.29%`
- 热点变化：
  - `step_env.actions`: `-6.93%`
  - `step_env.actions.read.read_response`: `-6.10%`
  - `step_env`: `-2.07%`

阶段结论（截至当前）：
- 已确认的有效增益点：
  1) 观测字段按需裁剪  
  2) feature layer 预分配  
  3) 单控制器 no-op 动作过滤  
- `RequestAction` 容器复用与 `unpack_layer` 微调在当前环境下未观察到正收益，暂不纳入主线优化。

### Phase 1 评测口径收敛（固定 race + repeats=7）

为降低近期“全链路同向波动”导致的误判，新增固定口径基线：
- `tests/profiles/profile_env_step_phase1_baseline_fixed7_smacnt_raw.txt`
- `tests/profiles/profile_env_step_phase1_baseline_fixed7_smacnt.json`
- `tests/profiles/profile_env_step_phase1_baseline_fixed7_smacnt.csv`

执行参数：
- `--agent_race=protoss --bot_race=terran --steps=2000 --repeats=7 --seed=20260227`

聚合结果（当前主线）：
- `Total Time mean/median/std`: `18.0345 / 18.1362 / 0.4755 s`
- `SPS mean/median/std`: `110.98 / 110.28 / 2.91`
- `Latency Mean mean/median/std`: `8.0282 / 7.9608 / 0.3556 ms`
- `Latency P99 mean/median/std`: `11.2182 / 10.9860 / 0.6257 ms`

执行策略更新：
- Phase 1 候选优化以该固定口径做 A/B，优先看 **median** 与 `step_env` 子项的同向变化。
- 若候选优化仅在单次或单 seed 见效、跨 seed 不稳定，则不进入主线。

## 1. 目标与基线

本阶段目标：以 `smacnt`（Python 3.14 + protobuf `upb`）为主优化目标，对 `pysc2-compat` 的 `env.step` 路径做持续提速，并能稳定对比“最新版 vs 历史版”。

当前基线来自：
- `tests/profiles/profile_env_step`
- `tests/profiles/profile_original`

其中 `benchmark_env_step.py` 的 `smacnt` 基线为：
- `Total Time`: `17.3919 s`
- `Average SPS`: `115.00`
- `Latency Mean/P50/P99`: `7.5485 / 7.3493 / 11.1290 ms`

说明：
- 历史 `profile_original` 是 `benchmark_observe.py`（不同脚本），可用于追踪协议层读写/解析趋势，但不与 `env_step` 直接做绝对值对比。

## 2. smacnt 瓶颈分解（来自现有 profile）

`step_env` 总耗时：`15.0907 s`（2000 steps）

主要子项占比（相对 `step_env`）：
- `step_env.observe.read.read_response`: `10.9385 s`（`72.49%`）
- `step_env.transform_obs`: `1.6201 s`（`10.74%`）
- `step_env.actions`: `1.3307 s`（`8.82%`）
- `step_env.step`: `0.7950 s`（`5.27%`）
- `step_env.transform_action`: `0.1095 s`（`0.73%`）
- `step_env.observe.read.parse_response`: `0.0600 s`（`0.40%`）

额外观察：
- `Total Time - env.step累计` 约 `2.2949 s`（`13.2%`）是 agent 端与循环控制开销，不在环境核心路径内。

结论：在 `smacnt` 上，protobuf 解析已经不是主瓶颈；优化重点应转向：
1) `read_response` 的等待/往返成本  
2) `transform_obs` 的 Python 对象构造与数组分配成本  
3) `actions` 路径中的请求封装与调用路径开销

## 3. 逐文件优化改进点

### `pysc2/env/sc2_env.py`

**现状（热点关联）**
- `step()` 每步都走通用多智能体路径：动作转换、`_parallel.run`、`_step`、`_observe`。
- 即使单智能体场景，也会构建多层 list/generator，再走统一分发。

**可行优化点**
1. 单智能体 fast-path（高优先）
   - 对 `len(_controllers)==1 and _num_agents==1` 走直接调用路径，避免每步构造 generator、zip、嵌套 list。
2. `step()` 动作封装降分配（中优先）
   - 当前每步构建 `[[...]]` 结构，可在单 agent 情况下降为扁平路径，减少对象创建。
3. 可选“信任动作”模式（中优先）
   - 与 `ensure_available_actions` 配合，允许在受控训练中跳过部分动作可用性检查。

**预估收益（smacnt）**
- `+1% ~ +3%`（主要来自 Python 调度/对象分配减少）。

**风险**
- 需保证单/多智能体行为一致；加入回归测试（单 agent、双 agent、realtime/non-realtime）。

---

### `pysc2/lib/remote_controller.py`

**现状（热点关联）**
- `observe/step/actions` 每步构造新的 protobuf request（`RequestObservation`、`RequestStep`、`RequestAction`）。
- `observe()` 中 stub 分支使用 `deepcopy`（虽不常触发，但触发时较重）。

**可行优化点**
1. request 对象复用池（高优先）
   - 复用 `RequestObservation`/`RequestStep` 外层对象，仅更新变化字段，降低每步分配。
2. `actions` 封装复用（中优先）
   - 在单 action 高频场景复用 `RequestAction` 容器并替换内部 repeated 字段。
3. stub 观测拷贝降级（低优先）
   - 仅在确需时深拷贝，优先浅拷贝 + 定向字段覆盖（需严格验证正确性）。

**预估收益（smacnt）**
- `+0.5% ~ +2%`。

**风险**
- protobuf repeated 字段复用容易引入脏数据；必须做字段清理和测试。

---

### `pysc2/lib/protocol.py`

**现状（热点关联）**
- `send()` 每次通过 `sc_pb.Request(**kwargs)` 构造新请求对象。
- `_read()` 中 `Response.FromString()` 每步创建新响应对象。
- 目前 `parse_response` 在 `smacnt` 已很低（0.4% of `step_env`）。

**可行优化点**
1. 增加 `send_prebuilt()`（中优先）
   - 对热路径直接发送预构建 `Request`，减少 kwargs->proto 构造。
2. 评估 `ParseFromString` 复用对象（低优先，实验性）
   - 仅在确认语义完全一致时使用；预计收益有限。

**预估收益（smacnt）**
- `+0.3% ~ +1%`。

**风险**
- 协议层变更风险高；需重点验证 request id/响应匹配、异常路径。

---

### `pysc2/lib/features.py`

**现状（热点关联）**
- `transform_obs` 是 `smacnt` 下最主要的 Python 侧热点（`1.6201 s`）。
- `feature_screen` / `feature_minimap` 逐层 `unpack -> astype -> stack`，分配频繁。
- `feature_units` 路径包含大量 Python 循环和 `Point/Transform` 对象运算。
- `available_actions/last_actions/score/ui` 默认都生成，即使训练不全用。

**可行优化点**
1. 观测字段按需生成（高优先）
   - 在 `AgentInterfaceFormat` 增加/启用细粒度开关，允许跳过 `score/ui/last_actions/available_actions` 中不需要的字段。
2. feature layer 预分配与批量写入（高优先）
   - 避免每层先建临时数组再 `np.stack`；改为预分配目标张量并逐层填充。
3. 减少不必要 dtype 扩张（中优先）
   - 当前大量层转为 `int32`，可引入“保留原生 dtype”模式（默认保持兼容，开关启用优化）。
4. `feature_units` 标量化/向量化混合改造（中高优先）
   - 将高频坐标变换改为标量快速路径，减少 `Point.build` 和链式对象运算。
5. `available_actions` 缓存（中优先）
   - 对 `obs.abilities` 形成 canonical key（例如有序 tuple）做短期缓存，降低重复映射开销。

**预估收益（smacnt）**
- `+4% ~ +10%`（最大潜力区）。

**风险**
- 该文件影响面最大；需要保证观测张量内容与 shape 完全兼容旧行为。

---

### `pysc2/lib/named_array.py`

**现状（热点关联）**
- `NamedNumpyArray` 每次构造会做 names 校验和索引映射构建。
- 在 `transform_obs` 高频调用下，这部分是可见固定成本。

**可行优化点**
1. 可选“纯 ndarray 输出”模式（高优先）
   - 训练/benchmark 模式下跳过命名包装，仅返回 `np.ndarray`/`dict[str, np.ndarray]`。
2. 名称元数据静态缓存（中优先）
   - 相同 shape+names 复用索引映射，减少重复构建。

**预估收益（smacnt）**
- `+1% ~ +4%`（依赖具体观测字段配置）。

**风险**
- 需要兼容依赖命名索引的用户代码；建议通过开关渐进启用。

---

### `pysc2/lib/run_parallel.py`

**现状（热点关联）**
- `len(funcs)==1` 时虽不启线程，但仍会构造列表和 `functools.partial`。
- 单智能体场景下每步都会经过这一层。

**可行优化点**
1. 单任务零分配路径（中优先）
   - 新增 `run_single(func_or_tuple)`，避免构造中间 list/partial。
2. 调用侧联动优化（中优先）
   - `sc2_env` 在单 controller 下直接调用，不走 `run_parallel`。

**预估收益（smacnt）**
- `+0.5% ~ +1.5%`。

**风险**
- 低风险，主要是接口兼容和测试补齐。

---

### `pysc2/lib/transform.py` 与 `pysc2/lib/point.py`

**现状（热点关联）**
- 坐标转换通过 `Point` 对象和链式 `Transform` 完成，表达清晰但对象创建偏多。
- 在 `feature_units/effects/radar` 路径中会频繁调用。

**可行优化点**
1. features 热路径内联标量变换（中优先）
   - 在热点循环里直接用标量算式，减少 `Point.build`/`Point` 运算对象。
2. 批量坐标转换接口（低到中优先）
   - 增加数组化转换 API（numpy 向量化），供 `feature_units` 批处理调用。

**预估收益（smacnt）**
- `+0.5% ~ +2%`（与 `feature_units` 使用密度相关）。

**风险**
- 需要防止坐标取整语义变化（`floor`/`PixelToCoord` 行为需一致）。

---

### `pysc2/lib/actions.py`

**现状（热点关联）**
- `transform_action` 中参数校验和映射逻辑偏通用，热路径下每步执行。
- 目前占比不高，但可作为低风险增量优化点。

**可行优化点**
1. 预编译参数校验器（中优先）
   - 按 function id 预生成参数验证函数，减少分支判断。
2. 受控场景校验裁剪（低到中优先）
   - 与 `ensure_available_actions=False` 联动，减少重复 availability/范围检查。

**预估收益（smacnt）**
- `+0.3% ~ +1.2%`。

**风险**
- 错误动作可能更晚暴露；需要用 debug 模式保留严格校验。

---

### `pysc2/bin/benchmark_env_step.py`

**现状（评测方法风险）**
- 使用 `RandomAgent` + 随机 race，回合进程复杂度会抖动（跨 run 可比性偏弱）。
- 当前输出以文本为主，不利于自动历史对比。

**可行优化点（评测基建）**
1. 固定随机种子（高优先）
   - 固定 `numpy/random`、环境 `random_seed`、race 配置。
2. 增加 warmup + 重复次数（高优先）
   - 例如 warmup 300 steps，正式 3~5 次取中位数。
3. 增加结构化输出（高优先）
   - 追加 JSON/CSV 输出：总时间、SPS、P50/P99、stopwatch关键项、环境元信息（python/protobuf backend）。
4. 标准化历史落盘命名（高优先）
   - `tests/profiles/profile_env_step_<YYYYMMDD_HHMM>_<env>.txt/json`

**预估收益**
- 这部分主要提升评测可信度，不直接提升运行速度。

---

### `pysc2/lib/stopwatch.py`

**现状**
- benchmark 里显式 `stopwatch.sw.enable()`，会引入可测但可控的统计开销。

**可行优化点**
1. 评测场景保留，训练场景默认关闭（中优先）
2. 如需线上开启，考虑采样记录（低优先）

**预估收益**
- 训练场景可减少轻微开销；benchmark 场景不建议关闭，否则失去分项数据。

## 4. 推荐执行顺序（按投入产出比）

### Phase 0（先做，低风险高收益）
1. `benchmark_env_step.py`：确定性 + 多次重复 + 结构化结果落盘。  
2. `features.py`：按需字段开关（先从 `score/ui/last_actions` 入手）。  
3. `sc2_env.py` + `run_parallel.py`：单智能体 fast-path。  

目标：`smacnt` 基线 `115 SPS -> 120~125 SPS`（约 `+4% ~ +9%`）。

### Phase 1（中风险，中高收益）
1. `features.py`：feature layer 预分配写入、dtype 策略。  
2. `features.py` + `transform.py`：feature_units 坐标变换降对象化。  
3. `named_array.py`：可选 plain ndarray 模式。  

目标：在 Phase 0 基础上再提升 `+5% ~ +12%`。

### Phase 2（高风险，小到中收益）
1. `remote_controller.py` + `protocol.py`：request/response 对象复用实验。  
2. 校验协议兼容、异常路径、长稳运行。  

目标：再提升 `+1% ~ +3%`，并降低长时间运行抖动。

## 5. 最新版与历史版对比规范（后续推进沿用）

建议统一使用以下“对比三件套”：
1. **固定参数**：`map/steps/step_mul/resolution/seed` 固定。  
2. **固定输出**：每次都保存 raw log + JSON summary。  
3. **固定口径**：对比 `Total Time/SPS/Latency(P50,P99)` + `step_env` 子项。

最小可执行流程：
1. 跑新版：输出到 `tests/profiles/profile_env_step_<timestamp>_smacnt_raw.txt`  
2. 解析新版和基线（`tests/profiles/profile_env_step_smacnt_raw.txt`）  
3. 生成对比摘要并追加到同目录 `*_compare.md`  

首个历史基线建议：
- `tests/profiles/profile_env_step_smacnt_raw.txt`（当前 smacnt 基线）
- `tests/profiles/profile_env_step`（人工汇总版）

---

如果按这个文档推进，下一步建议先做 Phase 0 的第 1 项（benchmark 结果结构化和可复现），这样后续每一个优化 commit 都能被可靠量化。  
