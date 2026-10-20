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

### 已落地（Phase 1 - feature_units 坐标变换降对象化）

本轮在 `pysc2/lib/features.py` 为 `feature_units/feature_effects/cargo_units` 增加了标量坐标快路径：
- 缓存 `world_camera_rel_to_feature_screen` 的 `scale/offset`
- 新增 `_world_to_feature_screen_xy()` 与 `_world_to_feature_screen_radius()`
- 在 `feature_screen` 相关路径中，跳过 `Point.build -> Chain.fwd_pt -> PixelToCoord` 的多层对象构造，直接做等价标量计算（保留 `floor` 语义）

对照口径（固定 race + `repeats=7`）：
- 基线：`tests/profiles/profile_env_step_phase1_baseline_fixed7_smacnt.json`
- 本轮：`tests/profiles/profile_env_step_phase1_featurecoords_fixed7_smacnt.json`

结果（new vs baseline）：
- `Total Time mean/median`: `-0.68% / -0.81%`
- `SPS mean/median`: `+0.65% / +0.81%`
- `Latency Mean mean/median`: `-0.77% / -1.04%`
- `Latency P99 mean/median`: `-1.25% / +0.38%`

热点变化（按 run 平均）：
- `step_env`: `-0.77%`
- `step_env.transform_obs.feature_units`: `-11.70%`
- `step_env.actions`: `-1.68%`
- `step_env.step`: `-2.88%`

结论：
- 该改动在固定口径下呈现小幅正收益，且 `feature_units` 子项有明显下降，可纳入 Phase 1 主线。
- 尾延迟 `P99` 的 median 仍有轻微波动，后续与下一项优化合并验证时继续观察。

### 已落地（Phase 1 - feature_units/raw_units 预分配写入）

本轮继续在 `pysc2/lib/features.py` 降低中间对象分配：
- `feature_units`：由 `list` 收集改为先计数、再预分配 `np.empty((N, len(FeatureUnit)))` 并逐行写入
- `raw_units`：由 `list -> numpy` 改为直接预分配并逐行写入（保留原 `to_list/to_numpy` stopwatch 分段）

对照口径（固定 race + `repeats=7`）：
- 上一版（featurecoords）：`tests/profiles/profile_env_step_phase1_featurecoords_fixed7_smacnt.json`
- 本轮：`tests/profiles/profile_env_step_phase1_unitarray_fixed7_smacnt.json`

结果（new vs featurecoords）：
- `Total Time mean/median`: `-1.61% / -2.36%`
- `SPS mean/median`: `+1.63% / +2.42%`
- `Latency Mean mean/median`: `-1.65% / -2.97%`
- `Latency P99 mean/median`: `-1.43% / -1.04%`

热点变化（按 run 平均）：
- `step_env`: `-1.66%`
- `step_env.transform_obs`: `-2.28%`
- `step_env.transform_obs.feature_units`: `-2.65%`
- `step_env.actions`: `-3.97%`
- `step_env.step`: `-8.90%`

累计效果（vs `phase1_baseline_fixed7`）：
- `Total Time mean/median`: `-2.28% / -3.15%`
- `SPS mean/median`: `+2.29% / +3.25%`
- `Latency Mean mean/median`: `-2.41% / -3.99%`
- `step_env.transform_obs.feature_units`: `-14.04%`

结论：
- 该优化在固定口径下显示稳定正收益，可作为 Phase 1 的第二个主线增益点。

### 已落地（Phase 1 - full_unit_vec 字段写入去重复计算）

本轮继续在 `pysc2/lib/features.py` 优化 `full_unit_vec` 热路径：
- 预绑定 `RAW_ABILITY_ID_TO_FUNC_ID` 映射与 `FeatureUnit` 长度，减少循环内全局查找
- 将 `orders/buff_ids` 读取改为一次性局部缓存，去掉重复 `len(...)` 和重复索引
- 复用已有预分配路径：`feature_units` 改为单次遍历填充 + 末尾切片（避免额外计数遍历）

对照口径（固定 race + `repeats=7`）：
- 上一版（unitarray）：`tests/profiles/profile_env_step_phase1_unitarray_fixed7_smacnt.json`
- 本轮：`tests/profiles/profile_env_step_phase1_unitvecopt_fixed7_smacnt.json`

结果（new vs unitarray）：
- `Total Time mean/median`: `-0.92% / -1.42%`
- `SPS mean/median`: `+0.95% / +1.44%`
- `Latency Mean mean/median`: `-0.99% / +0.69%`
- `Latency P99 mean/median`: `-1.53% / -1.57%`

热点变化（按 run 平均）：
- `step_env`: `-0.99%`
- `step_env.transform_obs`: `-3.14%`
- `step_env.transform_obs.feature_units`: `-21.59%`
- `step_env.actions`: `-3.67%`

累计效果（vs `phase1_baseline_fixed7`）：
- `Total Time mean/median`: `-3.18% / -4.53%`
- `SPS mean/median`: `+3.26% / +4.74%`
- `Latency Mean mean/median`: `-3.37% / -3.33%`
- `Latency P99 mean/median`: `-4.15% / -2.23%`
- `step_env.transform_obs.feature_units`: `-32.60%`

结论：
- 该优化在固定口径下进一步拉低 `feature_units` 子项，且整链路指标继续同向改善，可纳入主线。

### 已落地（Phase 1 - NamedNumpyArray 名称索引缓存）

本轮在 `pysc2/lib/named_array.py` 增加了构造期缓存：
- 新增 `_INDEX_NAMES_CACHE` 与 `_names_cache_key(...)`
- 对重复形状与重复 names 组合复用索引映射构建结果，减少 `NamedNumpyArray` 每步重复校验与重建
- 兼容性校验：`tests/lib/test_named_array.py` 全量通过（27/27）

对照口径（固定 race + `repeats=7`）：
- 上一版（unitvecopt）：`tests/profiles/profile_env_step_phase1_unitvecopt_fixed7_smacnt.json`
- 本轮：`tests/profiles/profile_env_step_phase1_namedcache_fixed7_smacnt.json`

结果（new vs unitvecopt）：
- `Total Time mean/median`: `-0.96% / +0.08%`
- `SPS mean/median`: `+1.04% / -0.08%`
- `Latency Mean mean/median`: `-1.16% / -1.84%`
- `Latency P99 mean/median`: `-0.83% / -1.43%`

结论：
- 该项单独收益较弱、mean/median 存在轻微分歧；后续通过“缓存开/关”与叠加优化一起复核。

### 已落地（Phase 1 - _update_camera 标量快路径）

在 `pysc2/lib/features.py` 中将 `_update_camera()` 改为标量计算，避免每步 `Point` 链式运算：
- 将 `self._update_camera(point.Point.build(raw.player.camera))` 改为直接传 `raw.player.camera`
- 用 `map_size_y` 与标量表达式直接构建 `offset`，减少临时对象

对照口径（固定 race + `repeats=7`）：
- 上一版（namedcache）：`tests/profiles/profile_env_step_phase1_namedcache_fixed7_smacnt.json`
- 本轮：`tests/profiles/profile_env_step_phase1_camera_fixed7_smacnt.json`

结果（new vs namedcache）：
- `Total Time mean/median`: `-0.07% / -0.57%`
- `SPS mean/median`: `+0.02% / +0.57%`
- `Latency Mean mean/median`: `-0.07% / -0.76%`
- `step_env.transform_obs.feature_units`: `-3.23%`

补充判断（缓存开/关复核）：
- 在相同代码下做 `named_array` 缓存开/关隔离对照后，缓存开启的 **median** 更优（`Total Time/SPS/Latency Mean` 同向），因此保留缓存版本进入主线。

累计效果（vs `phase1_baseline_fixed7`，当前主线）：
- `Total Time mean/median`: `-4.18% / -4.99%`
- `SPS mean/median`: `+4.35% / +5.25%`
- `Latency Mean mean/median`: `-4.57% / -5.83%`
- `Latency P99 mean/median`: `-5.60% / -2.63%`

### 已落地（Phase 1 - available_actions 能力映射缓存实验，默认关闭）

本轮在 `pysc2/lib/features.py` 增加了 `available_actions` 的能力映射缓存机制：
- 对 `obs.abilities` 构造 canonical key（`ability_id + requires_point`）
- 使用有界 `OrderedDict` 复用映射结果，减少重复遍历 `actions.ABILITY_IDS`
- 为保持可控性，新增 `available_actions_cache_size`（`0` 表示关闭）

同时在 `pysc2/bin/benchmark_env_step.py` 新增评测参数：
- `--obs_available_actions_cache_size`（默认 `0`，用于 A/B 隔离）

对照口径（固定 race，`steps=2000`）：
- fixed7（same seed，先 off 后 on）：
  - `tests/profiles/profile_env_step_phase1_availcache_off_fixed7_smacnt.json`
  - `tests/profiles/profile_env_step_phase1_availcache_on_fixed7_smacnt.json`
- fixed3（same seed，反向顺序先 on 后 off）：
  - `tests/profiles/profile_env_step_phase1_availcache_on_fixed3_smacnt.json`
  - `tests/profiles/profile_env_step_phase1_availcache_off_fixed3_smacnt.json`

结果摘要（on vs off）：
- **fixed7**：全链路退化  
  - `Total Time mean/median`: `+2.91% / +1.64%`  
  - `SPS mean/median`: `-2.83% / -1.61%`
- **fixed3（反向顺序）**：全链路改善  
  - `Total Time mean/median`: `-2.30% / -2.03%`  
  - `SPS mean/median`: `+2.36% / +2.07%`
- 两组中 `step_env.transform_obs.available_actions` 子项均明显下降（约 `-20% ~ -27%`）。
- **fixed8 + ABBA 交错（同进程）**：
  - `tests/profiles/profile_env_step_phase1_availcache_abba_fixed8_smacnt.json`
  - `Total Time mean/median`: `+0.78% / +0.82%`
  - `SPS mean/median`: `-0.76% / -0.81%`
  - `Latency Mean mean/median`: `+0.81% / +0.78%`
  - `Latency P99 mean/median`: `+1.20% / +2.16%`
  - 子项：`step_env.transform_obs.available_actions` `-17.91%`，但 `step_env.observe.read.read_response` `+2.94%`

结论：
- 该优化对子项有稳定收益，但全链路净效应不稳定；在 ABBA 交错口径下仍呈小幅负收益。
- 按 Phase 1 收敛规则，暂不作为默认主线增益；保留实现并通过参数开关继续观测（默认关闭）。

### 已落地（Phase 1 - benchmark A/B 交错模式）

为减少“先后顺序 + 系统负载”导致的误判，本轮在 `pysc2/bin/benchmark_env_step.py` 增加同进程 A/B 交错能力：
- `--obs_available_actions_cache_size_ab=A,B`：启用 A/B 模式（例如 `0,256`）
- `--obs_include_available_actions_ab=true,false`：可对观测开关做同口径 A/B
- `--obs_reuse_available_actions_result_ab=true,false`：可对“同帧可用动作复用”做同口径 A/B
- `--pipeline_actions_and_step_ab=true,false`：可对 action+step 管线化做同口径 A/B
- `--pipeline_step_and_observe_ab=true,false`：可对 step+observe 管线化做同口径 A/B
- `--reuse_step_observe_requests_ab=true,false`：可对 step/observe 请求对象复用做同口径 A/B
- `--ab_pattern=abab|abba`：控制运行顺序（推荐 `abba` 做镜像抵消）
- 输出 JSON 新增：
  - `config.run_cache_size_schedule`（每个 run 的 cache size 序列）
  - `config.run_include_available_actions_schedule`（每个 run 的 include 开关序列）
  - `config.run_reuse_available_actions_result_schedule`（每个 run 的 reuse 开关序列）
  - `config.run_pipeline_actions_and_step_schedule`（每个 run 的 pipeline 开关序列）
  - `config.run_pipeline_step_and_observe_schedule`（每个 run 的 step+observe pipeline 开关序列）
  - `config.run_reuse_step_observe_requests_schedule`（每个 run 的 request 复用开关序列）
  - `ab_test`（A/B 分组聚合 + `delta_pct_b_vs_a`）

示例命令（短烟测）：
- `conda run -n smacnt env PYTHONPATH=. python pysc2/bin/benchmark_env_step.py --agent_race=protoss --bot_race=terran --steps=200 --repeats=4 --seed=20260227 --obs_available_actions_cache_size_ab=0,256 --ab_pattern=abba --output_prefix=tests/profiles/profile_env_step_phase1_abtest_smoke_smacnt`

烟测产物：
- `tests/profiles/profile_env_step_phase1_abtest_smoke_smacnt.json`
- `tests/profiles/profile_env_step_phase1_abtest_smoke_smacnt.csv`

### 已落地（Phase 1 - available_actions 按需输出开关）

本轮在 `pysc2/lib/features.py` 增加了观测字段开关：
- `include_available_actions`（默认 `True`，保持兼容）
- 在 `observation_spec()` 与 `transform_obs()` 中按开关控制 `available_actions` 字段生成

同时在 `pysc2/bin/benchmark_env_step.py` 增加了：
- `--agent_type=random|noop`（`noop` 使用 `BaseAgent`，避免随机策略依赖 `available_actions` 字段）
- `--obs_include_available_actions=true|false`
- 兼容性保护：`agent_type=random` 且关闭 `available_actions` 时直接报错

对照口径（固定 race + `repeats=7`，`agent_type=noop`）：
- on：`tests/profiles/profile_env_step_phase1_availobs_on_noop_fixed7_smacnt.json`
- off：`tests/profiles/profile_env_step_phase1_availobs_off_noop_fixed7_smacnt.json`

结果（off vs on）：
- `Total Time mean/median`: `+0.44% / +2.44%`
- `SPS mean/median`: `-0.52% / -2.38%`
- `Latency Mean mean/median`: `+0.48% / +2.13%`
- `Latency P99 mean/median`: `-0.18% / -0.77%`
- 热点变化（按 run 平均）：
  - `step_env.transform_obs`: `-4.38%`
  - `step_env`: `+0.48%`
- **fixed8 + ABBA 交错（同进程，`agent_type=noop`）**：
  - `tests/profiles/profile_env_step_phase1_availobs_abba_noop_fixed8_smacnt.json`
  - `Total Time mean/median`: `+0.09% / +0.60%`（off 相对 on）
  - `SPS mean/median`: `-0.16% / -0.59%`
  - `Latency Mean mean/median`: `+0.03% / +0.27%`
  - `Latency P99 mean/median`: `-1.15% / -1.38%`
  - 热点：`step_env.transform_obs` `-6.85%`

结论：
- 关闭 `available_actions` 输出可稳定降低 `transform_obs` 子项耗时，但在 ABBA 交错口径下全链路仍未得到稳定正收益。
- 该开关保留（面向定制观测场景），主线默认仍保持 `include_available_actions=True`。

### 已落地（Phase 1 - benchmark 暴露 ensure_available_actions）

为验证“信任动作”路径在当前链路的收益，本轮将 `SC2Env` 的 `ensure_available_actions` 显式暴露到 benchmark：
- 新增参数：`--ensure_available_actions=true|false`（默认 `true`）
- 仅影响 `transform_action` 的可用性校验，不改变环境默认行为

对照口径（固定 race + random agent + `repeats=7`）：
- on：`tests/profiles/profile_env_step_phase1_ensureavail_on_fixed7_smacnt.json`
- off：`tests/profiles/profile_env_step_phase1_ensureavail_off_fixed7_smacnt.json`

结果（off vs on）：
- `Total Time mean/median`: `-0.10% / -0.79%`
- `SPS mean/median`: `+0.11% / +0.80%`
- `Latency Mean mean/median`: `-0.20% / -1.03%`
- `Latency P99 mean/median`: `+1.10% / +1.00%`
- 热点变化（按 run 平均）：
  - `step_env.transform_action`: `-51.82%`
  - `step_env.actions`: `-2.39%`
  - `step_env.observe.read.read_response`: `+0.51%`

结论：
- 关闭可用性校验可显著降低 `transform_action` 子项，但全链路净收益较弱且尾延迟略回退。
- 该项可作为受控训练场景的可选参数，不作为当前主线默认配置调整。

### 已落地（Phase 1 - available_actions 同帧结果复用实验，默认关闭）

本轮在 `pysc2/lib/features.py` 增加了“同一 observation 复用 `available_actions` 结果”的实验开关：
- `reuse_available_actions_result`（新增到 `AgentInterfaceFormat`，默认 `False`）
- 当开启时：`transform_obs()` 与 `transform_action()` 在同帧共享一次 `available_actions` 计算结果（按 observation 对象缓存）
- 保持安全回退：关闭时完全走原路径

同时在 `pysc2/bin/benchmark_env_step.py` 增加了评测参数：
- `--obs_reuse_available_actions_result=true|false`（默认 `false`）
- `--obs_reuse_available_actions_result_ab=true,false`

验证口径：
- 烟测：`tests/profiles/profile_env_step_phase1_availreuse_ab_smoke_smacnt.json`
- 正式：`fixed8 + ABBA`（同进程，random agent）
  - `tests/profiles/profile_env_step_phase1_availreuse_ab_fixed8_v2_smacnt.json`

AB 结果（B=false vs A=true，即关闭 vs 开启）：
- `Total Time mean/median`: `-0.08% / -0.34%`
- `SPS mean/median`: `+0.15% / +0.37%`
- `Latency Mean mean/median`: `+0.03% / -0.32%`
- `Latency P99 mean/median`: `+0.50% / +0.65%`

热点观察（按 run 平均）：
- `step_env.transform_action.available_actions`：关闭后恢复该子项（开启时为复用路径）
- `step_env.transform_obs`：关闭相对开启 `-14.14%`
- `step_env` 全链路：`+0.01%` 量级（接近持平）

结论：
- 子项层面呈现“此消彼长”，全链路净收益未形成稳定正向。
- 该开关保留用于后续联动实验（例如与 `ensure_available_actions` 组合），主线默认保持 `reuse_available_actions_result=False`。

### 已落地（Phase 1 - 单控 `action+step` 管线化实验，默认关闭）

本轮在 `pysc2/lib/protocol.py`、`pysc2/lib/remote_controller.py`、`pysc2/env/sc2_env.py` 增加了“单控制器 action+step 管线化”的实验路径：
- `StarcraftProtocol.send_multi(...)`：支持多请求背靠背发送并按 id 归并响应
- `RemoteController.actions_step(...)`：将 `RequestAction` 与 `RequestStep` 在一次调用内串行管线化
- `SC2Env` 新增 `pipeline_actions_and_step`（默认 `False`），仅在以下条件启用快路径：
  - 单控制器
  - 非 realtime
  - 无 action delay 配置、无延迟动作队列

同时在 benchmark 新增参数：
- `--pipeline_actions_and_step=true|false`（默认 `false`）
- `--pipeline_actions_and_step_ab=true,false`

验证口径：
- 烟测：`tests/profiles/profile_env_step_phase1_pipeactstep_ab_smoke_smacnt.json`
- 正式：`fixed8 + ABBA`（同进程，random agent）
  - `tests/profiles/profile_env_step_phase1_pipeactstep_ab_fixed8_smacnt.json`

AB 结果（B=true vs A=false，即开启 vs 关闭）：
- `Total Time mean/median`: `-3.94% / -3.85%`
- `SPS mean/median`: `+4.02% / +3.97%`
- `Latency Mean mean/median`: `-4.49% / -4.37%`
- `Latency P99 mean/median`: `-0.85% / -2.32%`

热点观察（按 run 平均）：
- `step_env`: `-4.54%`
- `step_env.actions + step_env.step` 组合耗时显著下降（合并到 `actions_step` 路径后整体更低）
- `step_env.observe.read.read_response`: `+1.05%`（小幅回升）

结论：
- 在 fixed8 + ABBA 口径下，该实验显示稳定正收益，且量级达到当前 Phase 1 中高价值候选。
- 由于调用路径有协议层改动，先保持环境默认 `pipeline_actions_and_step=False`，后续再做跨地图/多场景复验后决定是否提升为默认主线。

可迁移性复验（fixed8 + ABBA，同参数）：
- `AbyssalReef`：
  - `tests/profiles/profile_env_step_phase1_pipeactstep_ab_fixed8_abyssalreef_smacnt.json`
  - `Total Time mean/median`: `-2.36% / -2.18%`
  - `SPS mean/median`: `+2.18% / +2.14%`
  - `Latency Mean mean/median`: `-2.63% / -2.36%`
  - `Latency P99 mean/median`: `-0.93% / -0.51%`
- `Flat64`：
  - `tests/profiles/profile_env_step_phase1_pipeactstep_ab_fixed8_flat64_smacnt.json`
  - `Total Time mean/median`: `-2.61% / -3.07%`
  - `SPS mean/median`: `+2.75% / +3.31%`
  - `Latency Mean mean/median`: `-2.93% / -3.50%`
  - `Latency P99 mean/median`: `-2.10% / -2.59%`
- `CollectMineralShards`：
  - `tests/profiles/profile_env_step_phase1_pipeactstep_ab_fixed8_collectmineralshards_smacnt.json`
  - `Total Time mean/median`: `-7.43% / -7.53%`
  - `SPS mean/median`: `+8.05% / +8.17%`
  - `Latency Mean mean/median`: `-7.54% / -7.61%`
  - `Latency P99 mean/median`: `-15.10% / -16.24%`

复验结论：
- 在 3 个新增地图上，`pipeline_actions_and_step` 的全链路指标与 `Simple64` 一致为正向，未出现反向样本，具备可迁移性。
- `step_env.observe.read.read_response` 在各图均小幅上升（约 `+1% ~ +2%`），但被 `actions+step` 路径显著下降所覆盖，净效应稳定为正。

组合实验（`pipeline_actions_and_step` × `ensure_available_actions`）：
- `Simple64`，`ensure=false`：
  - `tests/profiles/profile_env_step_phase1_pipeactstep_ab_fixed8_ensureoff_smacnt.json`
  - `Total Time mean/median`: `-0.39% / +0.85%`
  - `SPS mean/median`: `+0.41% / -0.84%`
  - `Latency Mean mean/median`: `-0.42% / +0.98%`
  - `Latency P99 mean/median`: `-1.17% / +0.71%`
- `AbyssalReef`，`ensure=false`：
  - `tests/profiles/profile_env_step_phase1_pipeactstep_ab_fixed8_abyssalreef_ensureoff_smacnt.json`
  - `Total Time mean/median`: `+0.29% / -0.11%`
  - `SPS mean/median`: `-0.24% / +0.15%`
  - `Latency Mean mean/median`: `+0.40% / +0.04%`
  - `Latency P99 mean/median`: `-1.32% / -0.64%`
- `CollectMineralShards`，`ensure=false`：
  - `tests/profiles/profile_env_step_phase1_pipeactstep_ab_fixed8_collectmineralshards_ensureoff_smacnt.json`
  - `Total Time mean/median`: `-6.84% / -6.68%`
  - `SPS mean/median`: `+7.33% / +7.16%`
  - `Latency Mean mean/median`: `-6.96% / -6.82%`
  - `Latency P99 mean/median`: `-11.15% / -10.69%`

组合结论：
- `ensure_available_actions=false` 下，pipeline 收益呈**地图依赖**：在 `Simple64/AbyssalReef` 收敛到近 0，而在 `CollectMineralShards` 仍保持显著正收益。
- 在 `Simple64/AbyssalReef`，相较 `ensure=true`，`step_env.observe.read.read_response` 的回升幅度由约 `+1%` 扩大到约 `+3% ~ +4%`，抵消了部分 action/step 路径收益；但在 `CollectMineralShards` 该回升不明显（约 `+0.83%`）。
- 最终建议：若考虑将 pipeline 作为通用默认能力，仍应以 `ensure_available_actions=true` 作为主评估口径；`ensure=false` 场景按地图特性单独启用。

准入复核（正确性 + 长稳）：
- 正确性单测（已通过）：
  - `tests/env/test_sc2_env.py`：新增 `PipelineActionsAndStepTest`，覆盖启用条件门控与 `step()` 分发路径
  - `tests/lib/test_protocol.py`：覆盖 `send_multi` 的按 id 归并、无 id 回退、异常 id 报错
  - `tests/lib/test_remote_controller_pipeline.py`：覆盖 `actions_step` 在有/无 actions 下的分支行为
- 长稳压测（`Simple64`, `steps=5000`）：
  - `random`, `repeats=6`：`tests/profiles/profile_env_step_phase1_pipeactstep_ab_long6_smacnt.json`
    - `Total Time mean/median`: `+3.95% / +4.78%`（B=true vs A=false）
  - `random`, `repeats=8`（严格 ABBA 镜像）：`tests/profiles/profile_env_step_phase1_pipeactstep_ab_long8_smacnt.json`
    - `Total Time mean/median`: `+0.92% / +2.79%`
  - `noop`, `repeats=8`：`tests/profiles/profile_env_step_phase1_pipeactstep_ab_long8_noop_smacnt.json`
    - `Total Time mean/median`: `+0.56% / +0.21%`
    - `step_env` 子项：`-0.85%`（但全链路未体现同向收益）

最终准入结论：
- `pipeline_actions_and_step` 在短程 fixed8 口径下可观，但长程（5000 steps）稳定性不足，暂不满足“通用默认开启”准入条件。
- 当前状态保持为：实现保留、默认关闭、按场景启用（特别是 `ensure=false` 需按地图评估）。

### 已落地（Phase 2 候选 - 单控 `step+observe` 管线化实验，默认关闭）

本轮针对 `read_response` 路径继续推进候选，新增“step+observe 管线化”实验能力：
- `RemoteController.step_observe(...)`：通过 `send_multi` 将 `RequestStep` 与 `RequestObservation` 串行管线化。
- `RemoteController.observe(...)`：抽取 `_postprocess_observation(...)`，与 `step_observe` 共享观测后处理语义。
- `SC2Env` 新增 `pipeline_step_and_observe`（默认 `False`），仅在以下条件启用快路径：
  - 单控制器
  - 非 realtime
  - 无 action delay 配置、无延迟动作队列
- `SC2Env._step(...)` 支持 `prefetched_obs` 直传，避免管线化后再次调用 `observe` RPC。

benchmark 新增参数：
- `--pipeline_step_and_observe=true|false`（默认 `false`）
- `--pipeline_step_and_observe_ab=true,false`

正确性单测（已通过）：
- `tests/lib/test_remote_controller_pipeline.py`
  - 新增 `test_step_observe_uses_send_multi`
- `tests/env/test_sc2_env.py`
  - 新增 `PipelineStepAndObserveTest`，覆盖启用条件门控与 `_step()` 分发

验证口径：
- 烟测：`tests/profiles/profile_env_step_phase2_stepobs_ab_smoke_smacnt.json`
- 正式：`fixed8 + ABBA`
  - `noop`：`tests/profiles/profile_env_step_phase2_stepobs_ab_fixed8_noop_smacnt.json`
  - `random`：`tests/profiles/profile_env_step_phase2_stepobs_ab_fixed8_random_smacnt.json`

AB 结果（B=false vs A=true，即关闭 vs 开启）：
- `noop`：
  - `Total Time mean/median`: `+3.92% / +3.24%`
  - `SPS mean/median`: `-3.89% / -3.16%`
  - `Latency Mean mean/median`: `+4.53% / +3.86%`
  - `Latency P99 mean/median`: `+5.89% / +5.61%`
- `random`：
  - `Total Time mean/median`: `+0.64% / +0.73%`
  - `SPS mean/median`: `-0.52% / -0.70%`
  - `Latency Mean mean/median`: `+0.82% / +0.72%`
  - `Latency P99 mean/median`: `+1.16% / +3.98%`

结论：
- 在 `fixed8 + ABBA` 口径下，该候选未形成正收益；`noop` 口径为稳定负向，`random` 口径也为轻微负向。
- 当前不进入跨地图与长稳准入复核，保持“实现保留、默认关闭”（`pipeline_step_and_observe=False`）。
- 后续若继续推进 `read_response`，优先转向“协议对象复用/解析路径减分配”类候选。

### 已落地（Phase 2 候选 - `step/observe` 请求对象复用实验，默认关闭）

本轮在 `protocol + remote_controller + sc2_env` 增加了“请求对象复用”候选，目标是减少热路径 protobuf 对象分配：
- `StarcraftProtocol`：
  - 新增 `send_prebuilt(name, req)`，支持发送预构建 `sc_pb.Request`（保留 id 分配与响应 id 校验）
  - `send_multi(...)` 扩展为同时支持 payload 是 `Request*` 或预构建 `Request`
- `RemoteController`：
  - 新增 `set_reuse_step_observe_requests(enabled)`
  - 维护可复用的 `Request(step=...)` 与 `Request(observation=...)` 容器
  - 在 `step/observe/step_observe/actions_step` 中接入复用路径
- `SC2Env`：
  - 新增 `reuse_step_observe_requests`（默认 `False`）
  - 在 `_launch_game()` 阶段将开关同步到 controller
- benchmark 新增参数：
  - `--reuse_step_observe_requests=true|false`（默认 `false`）
  - `--reuse_step_observe_requests_ab=true,false`

正确性单测（已通过）：
- `tests/lib/test_protocol.py`
  - 新增 `send_prebuilt` 与 `send_multi(预构建 Request)` 覆盖
- `tests/lib/test_remote_controller_pipeline.py`
  - 覆盖 request reuse 打开时 `step/step_observe` 的预构建请求分支

验证口径：
- 烟测：`tests/profiles/profile_env_step_phase2_reqreuse_ab_smoke_smacnt.json`
- 正式：`fixed8 + ABBA`
  - `noop`：`tests/profiles/profile_env_step_phase2_reqreuse_ab_fixed8_noop_smacnt.json`
  - `random`：`tests/profiles/profile_env_step_phase2_reqreuse_ab_fixed8_random_smacnt.json`
- 可迁移性复验（`random`, `fixed8 + ABBA`）：
  - `AbyssalReef`：`tests/profiles/profile_env_step_phase2_reqreuse_ab_fixed8_abyssalreef_smacnt.json`
  - `Flat64`：`tests/profiles/profile_env_step_phase2_reqreuse_ab_fixed8_flat64_smacnt.json`
  - `CollectMineralShards`：`tests/profiles/profile_env_step_phase2_reqreuse_ab_fixed8_collectmineralshards_smacnt.json`
- 长稳复核（`Simple64`, `steps=5000`, `ABBA`）：
  - `random`：`tests/profiles/profile_env_step_phase2_reqreuse_ab_long8_smacnt.json`
  - `noop`：`tests/profiles/profile_env_step_phase2_reqreuse_ab_long8_noop_smacnt.json`

AB 结果（`B=false vs A=true`，即关闭 vs 开启）：
- `fixed8`, `noop`：
  - `Total Time mean/median`: `-2.58% / -2.92%`
  - `SPS mean/median`: `+2.49% / +3.01%`
  - `Latency Mean mean/median`: `-2.90% / -3.24%`
  - `Latency P99 mean/median`: `-4.09% / -3.82%`
- `fixed8`, `random`：
  - `Total Time mean/median`: `-2.98% / -2.82%`
  - `SPS mean/median`: `+3.14% / +2.91%`
  - `Latency Mean mean/median`: `-3.25% / -3.43%`
  - `Latency P99 mean/median`: `-0.68% / -1.04%`
- 可迁移性（`random`）：
  - `AbyssalReef` `Total Time mean/median`: `-3.82% / -6.07%`
  - `Flat64` `Total Time mean/median`: `-2.38% / -4.36%`
  - `CollectMineralShards` `Total Time mean/median`: `-2.59% / -2.43%`
- 长稳（`Simple64`, `steps=5000`）：
  - `random` `Total Time mean/median`: `-3.62% / -6.33%`
  - `noop` `Total Time mean/median`: `-0.75% / -0.16%`

封板复核（默认开启试运行回归包）：
- 产物：
  - `fixed8`：`profile_env_step_phase2_reqreuse_defaulton_pack_ab_fixed8_{random,noop}_smacnt.json`
  - 跨图：`profile_env_step_phase2_reqreuse_defaulton_pack_ab_fixed8_{abyssalreef,flat64,collectmineralshards}_smacnt.json`
  - 长稳：`profile_env_step_phase2_reqreuse_defaulton_pack_ab_long8_{random,noop}_smacnt.json`
- 结果（仍是 `B=false vs A=true`，**`Total Time` 负值表示“关闭更快”**）：
  - `fixed8 random`: `+1.27% / +2.36%`（开启略优）
  - `fixed8 noop`: `-5.49% / -7.09%`（关闭显著更优）
  - `AbyssalReef random`: `-4.75% / -5.33%`
  - `Flat64 random`: `-1.98% / -4.95%`
  - `CollectMineralShards random`: `-0.61% / -1.25%`
  - `long8 random`: `-2.05% / -1.86%`
  - `long8 noop`: `-0.76% / +0.72%`（接近持平、方向不稳定）

阶段结论（更新）：
- 在封板回归口径下，`reuse_step_observe_requests` 的收益方向与量级不稳定，且多数关键口径显示“关闭更快”。
- **不满足通用默认开启准入条件**：当前状态回退为“实现保留、默认关闭、按场景手动启用”。
- 默认值回退验证：`tests/profiles/profile_env_step_phase2_reqreuse_defaultoff_smoke_smacnt.json`（不显式传参时，run 配置显示 `reuse_step_observe_requests=false`）。
- 默认开启试运行冒烟记录保留：`tests/profiles/profile_env_step_phase2_reqreuse_defaulton_smoke_smacnt.json`（仅用于执行链路验证，不作为准入依据）。

执行稳定性备注（`spawn aborted` 分析与修复建议）：
- 现象：长命令偶发 `Command failed to spawn: Aborted`，并非 benchmark 脚本内部异常（脚本未实际进入运行）。
- 取证：
  - 无 OOM / 无内核 killed process 记录
  - 系统资源与进程上限充足
  - 同命令重跑可成功，且 `--no-capture-output + PYTHONUNBUFFERED=1` 下稳定完成
- 推断：更可能是命令启动层（IDE/命令包装层）偶发性失败，而非 `pysc2-compat` 业务代码缺陷。
- 建议修复（执行层）：
  1. 长跑命令统一使用 `conda run --no-capture-output`
  2. 增加 `PYTHONUNBUFFERED=1` + `python -u`，避免长时间无输出
  3. 对长跑命令做“一次自动重试”策略（若 spawn 失败立即重跑）

准入后回归建议命令块（默认关闭基线）：
- 统一入口（带重试）：`tests/profiles/run_benchmark_env_step_retry.py`
  - 可通过 `SMACNT_ENV_NAME` 覆盖环境名（默认 `smacnt`）
  - 可通过 `BENCH_RETRY_ATTEMPTS` 配置重试次数（默认 `2`）
- 快速冒烟（默认关闭路径）：
  - `python tests/profiles/run_benchmark_env_step_retry.py --map=Simple64 --agent_type=noop --repeats=2 --warmup_steps=20 --steps=80 --output_prefix=tests/profiles/profile_env_step_phase2_reqreuse_defaultoff_smoke_smacnt`
- 固定口径 A/B（防漂移）：
  - `python tests/profiles/run_benchmark_env_step_retry.py --map=Simple64 --agent_type=random --repeats=8 --warmup_steps=200 --steps=2000 --ab_pattern=abba --reuse_step_observe_requests_ab=true,false --output_prefix=tests/profiles/profile_env_step_phase2_reqreuse_ab_fixed8_random_smacnt`
- 长稳口径（准入守门）：
  - `python tests/profiles/run_benchmark_env_step_retry.py --map=Simple64 --agent_type=random --repeats=8 --warmup_steps=200 --steps=5000 --ab_pattern=abba --reuse_step_observe_requests_ab=true,false --output_prefix=tests/profiles/profile_env_step_phase2_reqreuse_ab_long8_smacnt`
- 自动门禁（PASS/FAIL）：
  - `python tests/profiles/check_reqreuse_gate.py --fixed8-random tests/profiles/profile_env_step_phase2_reqreuse_ab_fixed8_random_smacnt.json --fixed8-noop tests/profiles/profile_env_step_phase2_reqreuse_ab_fixed8_noop_smacnt.json --long8-random tests/profiles/profile_env_step_phase2_reqreuse_ab_long8_smacnt.json`

`reuse_step_observe_requests` 手动启用策略（当前版本）：
- 默认策略：**保持关闭**（`reuse_step_observe_requests=false`）；当前无“通用白名单地图”。
- 启用前必须完成同配置 A/B（`true,false`，`abba`）并同时满足：
  1. `fixed8 random`：`Total Time mean >= +1.0%` 且 `median >= +1.0%`
  2. `fixed8 noop`：`Total Time mean >= -0.5%`（不允许明显反向）
  3. `long8 random`：`Total Time mean >= +0.5%`
  4. `long8 random`：`Latency P99 mean >= -2.0%`（允许轻微抖动，但不接受明显回归）
  说明：以上阈值使用 A/B 口径 `B=false vs A=true`；正值表示“关闭更慢/开启更快”，负值表示“关闭更快/开启更慢”。
- 生产启用方式（通过上述门槛后）：
  - 训练/评测命令显式传 `--reuse_step_observe_requests=true`
  - 每次升级依赖（Python/protobuf/SC2）后重新做一轮 A/B 复验
- 回退触发条件（任一满足即关闭）：
  - `Total Time mean` 回归 `> +1.0%`
  - `Latency P99 mean` 回归 `> +2.0%`
  - 同一 map 在 `random/noop` 方向持续分裂（一个正向、一个显著负向）

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
