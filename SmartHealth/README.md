# SmartHealth · 蓝天健康病理垂类多模态大模型与智慧医疗 Agent 平台

把多年积累、**已由医生完成标注**的病理切片，转化为可注册、可交付、可持续迭代的医疗 AI 能力。

本仓库是《蓝天健康病理垂类多模态大模型与智慧医疗Agent方案设计》的**代码实现**，
按设计文档 11 章的结构落地为 **15 个业务模块、69 张数据表、319 个 REST 接口**、1 条 WebSocket 通道与一个自包含控制台；支持**真实 WSI 读取**与**真实 ONNX 权重推理**。

---

## 一、快速开始

```bash
# 1) 后端依赖（Python 3.10+）
pip install -r requirements.txt

# 2) 装载演示数据（首次运行必须；--reset 会重建库）
python -m app.seed --reset            # 完整模式，约 3 分钟（含训练/推理/评测/联邦）
python -m app.seed --reset --quick    # 快速模式，约 40 秒

# 3) 启动后端（默认 127.0.0.1:8100）
python run.py                          # 接口文档 http://127.0.0.1:8100/docs

# 4) 启动前端控制台（零 npm 依赖）
cd frontend && node server.js          # http://127.0.0.1:8101
# 端口被占用时：node server.js --port 8477 --api http://127.0.0.1:8100
```

运维探针与指标（前端端口即可访问，已反代）：

```bash
curl http://127.0.0.1:8101/healthz    # 存活
curl http://127.0.0.1:8101/readyz     # 就绪（数据库/磁盘/作业引擎/调度器四项实测）
curl http://127.0.0.1:8101/metrics    # Prometheus 文本格式
```

演示账号：

| 账号 | 密码 | 角色 | 说明 |
|---|---|---|---|
| `admin` | `Admin@2026` | 系统管理员 | 全部权限 |
| `cmo` | `Cmo@2026` | 首席医学官 | 标签体系、终审判定、临床验证 |
| `algo01` | `Algo@2026` | 算法工程师 | 模型、流水线、评测、作业 |
| `doctor01` | `Doctor@2026` | 病理医师 | 阅片、终审、标注（限 SITE-A） |
| `reg01` | `Reg@2026` | 注册与合规专员 | 伦理台账、审计链、注册申报 |
| `ops01` | `Ops@2026` | 科室运营 | 只读查看运营看板与业务数据 |

> 前端端口默认 8101；若被占用，用 `node server.js --port <端口> --api http://127.0.0.1:8100`。

---

## 一·五、三种部署形态

| 形态 | 启动方式 | 适用 |
|---|---|---|
| 单进程 | `python run.py` | 演示、小院内；API 与作业 Worker 同进程 |
| 多进程 | `python run.py --workers 2` | 生产；N 个 API 进程 + 独立作业 Worker 进程 |
| 纯 Worker | `python -m app.worker --processes 2 --concurrency 4` | 单独扩缩作业算力 |

多进程下四件事由分布式锁/心跳保证（`GET /api/v1/system/deployment` 可自查）：

| 事项 | 机制 |
|---|---|
| 数据库迁移 | 迁移前抢 `smarthealth:migrate` 锁，多进程同时启动只有一个执行 |
| 周期任务 | 每个任务各自抢锁（leader-only），多实例不会重复执行 |
| 作业回收 | **按心跳判定**，启动时不会误杀兄弟进程正在执行的作业 |
| 作业领取 | PostgreSQL 用 `FOR UPDATE SKIP LOCKED`；SQLite 用读写分离的乐观更新 |
| 事件推送 | DB 为权威来源（可续传），Redis 可选（只降延迟，缺失不影响正确性） |

生产部署建议：

```bash
export SMARTHEALTH_DATABASE_URL="postgresql+psycopg://user:pwd@host:5432/smarthealth"
export SMARTHEALTH_REDIS_URL="redis://127.0.0.1:6379/0"
export SMARTHEALTH_DEPLOYMENT_ENV=product        # 启用非商用权重门禁
python scripts/doctor.py --require-redis         # 上线前预检
python run.py --workers 4                        # 4 API + 1 Worker（每进程 4 并发）
```

---

## 一·六、真实切片与真实权重

**真实 WSI**：把 `Slide.file_path` 指向院内切片即可，`open_slide()` 会按魔数+后缀
自动选择后端（openslide > tifffile > pillow > numpy）。tifffile 路径实现了
**分块区域读取**——读一个 128×128 图块只解码 1—4 个 tile，不会加载整层
（L0 可达数十 GB，整层加载必然 OOM）。

```bash
python scripts/make_sample_wsi.py --size 4096 --levels 4   # 生成真实金字塔 TIFF 样例
python scripts/selftest_wsi.py                             # 逐像素验证读取正确性
```

**真实权重**：走模型清单治理，不硬编码在代码里。

```bash
python scripts/model_registry.py sync                      # 同步内置声明到清单
python scripts/model_registry.py export-reference          # 导出自研参照 ONNX（真实计算图）
python scripts/model_registry.py install hibou-b-onnx --from D:/weights/hibou-b.onnx
python scripts/model_registry.py verify --all              # 校验文件/校验和/ONNX 结构/维度
python scripts/model_registry.py license-audit             # 哪些能进商用主线
```

在 `product` 环境安装非商用权重（UNI2-h / Virchow2 / GigaPath 等）会被**直接拒绝**，
并给出两条可选做法；显式传 `--stage research` 才放行且记 warning。

---

## 一·七、实时作业事件

```bash
curl -N "http://127.0.0.1:8100/api/v1/jobs/stream?token=<access>&after_id=0"   # SSE
curl    "http://127.0.0.1:8100/api/v1/jobs/events?after_id=0"                  # 游标拉取
ws://127.0.0.1:8100/api/v1/ws/jobs                                            # WebSocket
```

前端任务中心默认用 SSE（毫秒级推送），连不上时自动回落游标轮询，
并在标题栏显示当前通道与游标，用户能区分「没有事件」和「通道断了」。

---

## 一·八、CI 与上线门禁

CI 的检查项写在 `scripts/ci.sh` 里，流水线配置只是它的薄壳 —— 这样**本地与 CI 完全一致**，
排查时把 CI 最后一行命令抄下来就能复现（换平台也不用重写检查逻辑）。

```bash
bash scripts/ci.sh fast        # 每次推送：SQLite，零外部服务
bash scripts/ci.sh staging     # 主干/MR：真实 PostgreSQL + Redis
bash scripts/ci.sh release     # 打 tag：上线门禁
```

| 档位 | 需要 | 覆盖内容 | 实测耗时 |
|---|---|---|---|
| `fast` | 无 | 迁移幂等、doctor、PG 方言编译、接口自测、前端契约 | ≈ 6 分钟 |
| `staging` | **PG + Redis** | 上面的全部 + **SKIP LOCKED 领取**、真实并发写、Redis 分布式锁、多进程 Worker、SSE/WS 实时通道 | ≈ 10 分钟 |
| `release` | **PG + Redis** | 上面的全部 + 真实金字塔 TIFF 逐像素读取、真实 ONNX 推理、权重治理与许可门禁，末关 `--fail-on-warn` | ≈ 13 分钟 |

`staging` / `release` **强制要求** PG 与 Redis，缺了直接退出码 2 并说明原因：
用 SQLite 跑这两档，SKIP LOCKED 与分布式锁一次都不会执行，全绿也不能作为上线依据。

### doctor 作为上线门禁

```bash
# 本地排障（人读）
python scripts/doctor.py

# CI 里做门禁：不满足即 FAIL，阻止发布
python scripts/doctor.py --ci --require-postgres --require-redis --fail-on-warn
```

| 参数 | 作用 |
|---|---|
| `--ci` | 紧凑输出 + 末尾稳定摘要行（`DOCTOR_SUMMARY ok=… fail=… warn=…`） |
| `--require-postgres` | 数据库必须是 PG（防止 CI 忘了配 PG，SQLite 也能"全绿"） |
| `--require-redis` | Redis 必须可用，**且分布式锁功能完整** |
| `--fail-on-warn` | 最严格：WARN 也算不通过 |
| `--init-db` | 先执行迁移（全新环境/CI 首次运行用） |

退出码语义（门禁工程的第一原则：判不出"该不该拦"的门禁等于没有）：

| 码 | 含义 |
|---|---|
| 0 | 通过 |
| 1 | **门禁未通过**（有 FAIL 项）→ 阻止发布 |
| 2 | **门禁本身跑不起来**（参数/依赖缺失）→ 与"环境不合格"区分开，避免误报 |

`--require-redis` 检查的不只是连通性，而是**功能往返**：抢锁 → 竞争方被拒 → 非持有者释放被拒 →
持有者释放 → 释放后可重抢 → 续期可用。因为 ping 正常但 **ACL 禁了 EVAL** 时，
Lua 释放会失败、锁一直泄漏到租约到期，而报错只会是"未能获取锁"，极易被误判成业务问题。

### 平台配置

本项目位于 monorepo [`ericyudong/AI-Coding`](https://github.com/ericyudong/AI-Coding)
的 `SmartHealth/` 子目录下。**这一点直接决定了 workflow 该放在哪** ——
GitHub Actions 只扫描仓库根的 `.github/workflows/`，子目录里的 workflow 不会被加载：

| 平台 | 文件 | 说明 |
|---|---|---|
| GitHub Actions（**真正生效的**） | monorepo 仓库根的 `.github/workflows/smarthealth-ci.yml` | `fast` 每次推送；`staging` 带 postgres/redis service；`release` 绑定 `environment: release` 供人工批准 |
| GitHub Actions（单库版） | `.github/workflows/ci.yml` | 与上面同一份逻辑。**在 monorepo 中不会被执行**；保留它是为了 SmartHealth 拆成独立仓库时开箱即用 |
| GitLab CI | `.gitlab-ci.yml` | 同三档。在 monorepo 中需由根级配置 `include: local:` 拉入，或拆库后放到新仓库根 |
| 其它（Jenkins / CNB / Gitee Go …） | 无需新文件 | 直接执行 `bash scripts/ci.sh <profile>`，环境变量见下 |

monorepo 接入靠三件事，缺一不可：

1. **根级薄壳**：workflow 放仓库根，逻辑仍只在 `SmartHealth/scripts/ci.sh` 里；
2. **`defaults.run.working-directory: SmartHealth`**：把每个 `run` 步骤钉在子项目目录，
   于是 `bash scripts/ci.sh fast` 的语义与单库时完全一致；
3. **`paths` 过滤 + tag 前缀收窄**：只有 `SmartHealth/**` 的改动才触发，其它子项目的
   提交不会被牵连。tag 触发限定为 `SmartHealth-v*` —— 顺带一提，GitHub 的**路径过滤
   对 tag 推送不生效**（官方行为），所以 tag 这一路只能靠前缀来收窄。

| 事件 | 跑什么 |
|---|---|
| 推送 / PR，且改动落在 `SmartHealth/**` 或该 workflow 自身 | `fast` + `staging` |
| 打 `SmartHealth-v1.0.0` 这类 tag | `fast` + `staging` + `release`（上线门禁） |
| 手动触发（Actions → Run workflow，选 profile） | 按所选档位决定跑哪几档 |

```bash
# 任意 CI 系统接入所需的环境变量（staging / release 档）
export SMARTHEALTH_DATABASE_URL="postgresql+psycopg://user:pwd@host:5432/smarthealth_ci"
export SMARTHEALTH_REDIS_URL="redis://host:6379/0"
export SMARTHEALTH_DEPLOYMENT_ENV="product"   # release 档会自动设置
bash scripts/ci.sh release
```

可调项：`PYTHON`（解释器）、`CI_SKIP_INSTALL=1`（跳过依赖安装）、`CI_SEED_MODE=quick|full`、
`CI_SEED_SKIP_MODEL=1`（冒烟档，种子从 5 分钟压到约 1 分钟）、`CI_KEEP_DB=1`（保留临时库排查）。

### 门禁的可信度设计

这三条是为了让"绿灯"真的可信，而不是让流水线看起来在跑：

1. **CI 在全新数据库上跑一遍装载** —— 这抓到了两个只在干净环境才暴露的缺陷：
   `recover_orphans` 误杀兄弟进程的作业（心跳判定）、以及 `EncoderRegistry` 缺列导致
   全新库装载直接崩溃（本地库已有数据所以从未触发）。
2. **staging 档强制 PG，并断言 `started` 事件里真的出现 `SKIP LOCKED` 字样** ——
   把"走了哪条代码分支"变成可验证事实，防止"配了 PG 却静默走通用路径"的绿灯空转。
3. **区分「声明的跳过」与「被迫的跳过」** —— 冒烟档主动缩小范围时返回
   `result=pass_with_declared_skips` 并放行；因上游失败而连带跳过的，一律 `result=fail`
   并列出根因，避免"4 个失败看起来像四处崩坏，实际只有一个根因"。

---

## 二、自测（可重复运行）

```bash
python scripts/selftest_api.py            # 后端端到端（83 项）
python scripts/selftest_frontend.py       # 前后端字段契约（54 项）
```

| 脚本 | 覆盖内容 | 当前结果 |
|---|---|---|
| `selftest_api.py` | 认证/RBAC、53 个列表接口、许可证门禁、Agent、评测、审计链、联邦、注册、运营看板、**异步作业全生命周期**、**上传与 CSV 导入**、**标注写入闭环与质控**、**刷新令牌与登录锁定**、**行级数据隔离**、**探针与指标** | **83 / 83 通过** |
| `selftest_frontend.py` | 控制台每个视图读取的字段是否真实存在（含任务中心/待办中心/标注工作台/数据范围） | **54 / 54 通过** |

> 两个脚本都必须用 `with TestClient(app)`：只有作为上下文管理器才会触发 lifespan，
> 而作业引擎与周期调度都在 lifespan 里启动。这一点写在脚本注释里，避免后人"优化"掉。

---

## 二·五、相对演示版做了哪些商用化改造

演示版的问题不是"功能少"，而是**只能看、不能干、出事查不出来**。本轮改造集中在五件事：

### 1. 异步作业体系（最关键的一处结构性改造）

原状：训练/推理/评测/联邦全在 HTTP 请求里同步跑，请求必然超时、没有进度、不能取消、进程重启即丢。

现在：`app/core/tasks.py` 提供持久化作业队列 + Worker 池。

| 能力 | 实现要点 |
|---|---|
| 持久化队列 | 作业落 `sys_async_job`，重启后排队作业继续调度，中断作业标记失败但保留重试 |
| 原子领取 | `UPDATE ... WHERE id=? AND status='queued'`，多 Worker/多进程不重复执行 |
| 真实进度 | 逐图块/逐轮次/逐张切片上报（节流为「变化≥1% 或间隔≥0.5s」），前端进度条不是假的 |
| 请求式取消 | 只置标志，Worker 在安全检查点退出，避免落库到一半被硬杀产生脏数据 |
| 分类重试 | 业务规则类失败（如「评测集缺预测结果」）**不**自动重试，避免同一错误刷两遍 |
| 心跳回收 | 心跳超时判定 Worker 失联并回收作业；启动时恢复孤儿作业 |
| 幂等提交 | `dedup_key` 命中未终态作业直接复用，连点两次只会跑一个 |
| 事件流 | 每次状态变化落一条事件，可完整回放「这个任务到底发生了什么」 |
| 优雅关闭 | 停止接单 → 请求在跑作业取消 → 等待落地 → 退出 |

业务接口默认异步（返回 202 + 作业句柄），传 `sync=true` 可同步执行（排障/测试用）。

### 2. 真实数据接入

- **切片文件上传**：流式落盘（4 GB 单文件不占内存）+ SHA256 去重（相同内容二次上传直接 409）+ 逐块进度
- **批量上传**：逐个处理并**逐项回报失败原因**（科室上传 200 个文件时必须知道哪 3 个失败、为什么）
- **CSV 元数据导入**：先「体检」再入库，定位到「第几行、哪一列、错在哪」；带 BOM 模板供 Excel 正确识别中文
- **删除保护**：有下游引用（标注/预测/Agent 会话）的切片默认拒绝删除，防止模型血缘断链——注册申报必须能回答「这个版本用了哪些数据」

### 3. 业务写闭环

- **标注工作台**：按 `LabelSchema` 校验值类型/值域/层级，逐条回报拒绝原因；**写入后立刻反馈注册必备标签缺口**（把合规问题暴露在标注现场，而不是半年后申报时）
- **质控闭环**：保存即入质控队列，判定不通过自动标记返工并回写切片状态
- **医生终审 / 仲裁**：从待办中心直达，全流程留痕

### 4. 商用安全基线

| 项 | 实现 |
|---|---|
| 双令牌 | 短 access（60 min）+ 长 refresh（14 天） |
| refresh 轮换 | 一次一换；**旧令牌被再次使用即判定泄露，强制该账号全量下线** |
| 会话管理 | 可列出自己的登录会话并逐个踢下线；令牌只存哈希 |
| 登录防爆破 | 连续失败达阈值锁定账号，记录每次尝试（含 IP） |
| 密码策略 | 返回「缺哪一条」而非笼统「不合规」；改密后吊销其他会话 |
| 接口限流 | 令牌桶，读/写/登录三档独立；超限返回 429 + `Retry-After` |
| 行级数据隔离 | `all / org / site` 三档数据范围，列表与**按 ID 直取**都受约束，越权返回 403 |

### 5. 运维可观测

- `/healthz` 存活探针（刻意不查数据库：DB 抖动不该导致容器被重启）
- `/readyz` 就绪探针，实测**数据库 / 磁盘余量 / 作业引擎 / 调度器**四项，不就绪返回 503
- `/metrics` Prometheus 文本格式（请求数/时延分位/错误率/队列深度）
- 周期任务：边缘节点心跳检测、队列积压告警、失联作业回收、过期令牌清理、作业事件归档、KPI 快照
- 结构化访问日志 + `X-Trace-Id`（响应头回传，前端在报错时一并显示，方便对日志）
- 前端作为唯一入口时也反代 `/healthz`、`/readyz`、`/metrics`（否则探针会被 SPA 回退成 200，监控看到"正常"但拿不到真实状态）

### 工程细节（容易踩但必须处理）

- **SQLite 锁升级会"立即失败"**：同一事务里先 SELECT 再 UPDATE 走的是锁升级路径，
  此时 SQLite **故意不等待 `busy_timeout`** 而立刻返回 `SQLITE_BUSY` ——
  这就是"配了 60s 超时却秒失败 database is locked"的原因。
  写路径统一走 `WriterSessionLocal`（`begin` 事件发 `BEGIN IMMEDIATE`，把升级变等待），
  作业领取改为读写分离。`isolation_level="IMMEDIATE"` 在 pysqlite 方言**不被接受**，只能用事件钩子。
- **作业回收按心跳判定**，不能"把所有 running 标失败"—— 那会误杀兄弟进程正在跑的作业。
- **权重安装用临时文件 + 原子替换**：否则校验失败时必须删 target，会把已装好的那份一起删掉。
- **许可门禁默认拒绝**：写成"只有明确装到商用目录才拦"等于没有门禁（不传目录时恒放行）。
- **SSE 的游标要一并与生成器下发**，只写进首帧会让每个新连接重放全部历史事件。
- **onnx.checker 通过 ≠ 能加载**：Gemm 的 `transB` 语义错误只有真正建 onnxruntime 会话才报。
- **tifffile 的 `segments()` 是按序解码的生成器**，做随机访问要用
  `dataoffsets` + `databytecounts` + `page.decode(raw, i)`。
- **行尾必须是 LF，靠 `.gitattributes` 兜住**：本地是 Windows（CRLF）、CI 是 Linux（LF）。
  没有 `* text=auto eol=lf` 时，带 CRLF 的 `scripts/ci.sh` 在 Linux 上第一行就崩 ——
  `$'\r': command not found` / `syntax error near unexpected token $'{\r'` ——
  而 Git Bash 里跑得完全正常，**本地复现不出来**。这不是理论风险：第一次真正跑
  GitHub Actions 时 `fast` 与 `staging` 两个 job 都在 20 秒内挂掉，就是死在这上面。
  同一类隐患还包括带 CR 的 `.gitignore`（模式因不可见字符匹配失败）与带 CR 的 YAML。
  落地时顺手把子树里 65 个 CRLF 文件统一成了 LF（原本 65 CRLF / 31 LF，是混合的）。
- **GitHub Actions 的 service 容器主机名语义**：job **直接跑在 runner 虚拟机上**时
  （没写 `container:`），服务容器只是"端口映射到宿主机"，**只能用 `localhost:<port>`**；
  写服务名 `postgres` / `redis` 会得到 `failed to resolve host 'postgres': Temporary
  failure in name resolution`。且服务健康检查是 `docker inspect` 在容器**内部**做的，
  日志里一切 Ready —— 具有极强的迷惑性。GitLab CI 相反：job 默认跑在镜像容器里，
  服务**别名**才对。两个平台语义不同，**不能照抄**（照抄正是 staging 档第一次
  在 GitHub 上挂掉的直接原因）。
- **字节列必须 `BigInteger`**：PostgreSQL 的 `INTEGER` 是 32 位（上限 2^31-1 ≈ 2.1 GB），
  而存储容量类数值——单张金字塔 WSI、批次总量、分层容量（cold 层数百 TB）、联邦累计
  上传——在真实规模下必然超出，插入时 `NumericValueOutOfRange`。SQLite 的 INTEGER
  本来就是 64 位，**这个 bug 在本地永远复现不出来**，只有 CI 的 staging 档（强制
  真实 PG）跑 seed 时才会暴露。已修：5 个字节列升 `BigInteger` + 迁移 v10
  （`widen_byte_columns`，PG 上 `ALTER COLUMN TYPE BIGINT`，SQLite 无需变更）。

- **SQLite 单写者**：Worker 的进度写入复用 handler 的会话（SAVEPOINT），否则会等待自己持有的写锁形成**自死锁**
- 启用 WAL + `busy_timeout=60s`，作业与 API 并发写库不再互相阻塞
- 事件序号惰性对齐已有最大值，避免与「入队/开始」事件撞号导致事件流次序不可信
- 统一错误体在 `detail` 为 dict 时**保留结构**（如删除被拒的 `references`），不 `str()` 拍平
- 长会话读作业状态用 `populate_existing` 强制重读，避免把「已完成」显示成「排队中」

---

## 二·六、模块清单（15 个）

| # | 模块 | 说明 |
|---|---|---|
| 00 | 总览 | 决策者关心的核心数字 |
| 01 | **任务中心** | 作业列表/进度/取消/重试/事件流 + 待办中心 |
| 02 | **数据接入** | 切片上传（单/批量）、CSV 体检与导入、模板下载 |
| 03 | **标注工作台** | 四层标注录入、schema 校验、质控判定与返工 |
| 04 | 数据资产 | 资产盘点、切片详情、注意力热力图 |
| 05 | 标签体系 | 标签定义、标注人员、SOP、一致性分析 |
| 06 | 模型与算力 | 基座/版本/许可体检/训练任务 |
| 07 | 推理流水线 | 特征库、批量推理、注意力热区、相似病例 |
| 08 | 智慧医疗 Agent | 五智能体会话、证据链、能力边界 |
| 09 | 评测基座 | 评测集、指标、跨中心衰减、MRMC 对照 |
| 10 | 合规与注册 | 伦理台账、审计链、可解释性、审评关口 |
| 11 | 云边协同 | 边缘节点、模型下发、联邦式增量微调 |
| 12 | 注册与路线图 | 注册路径、里程碑、风险台账、试验中心 |
| 13 | 运营看板 | KPI 快照、团队编制、成本结构、立项决策 |
| 14 | 系统管理 | 用户、角色、系统配置、数据字典、周期任务 |

---

## 三、目录结构

```
SmartHealth/
├── app/
│   ├── main.py                FastAPI 入口（建表 → 起作业引擎/调度器 → 挂路由 → 探针/指标 → 托管前端）
│   ├── seed.py / seed_data.py 演示数据装载（把文档数字变成可运行系统）
│   ├── core/
│   │   ├── tasks.py           异步作业引擎（队列/Worker/进度/取消/重试/恢复/优雅关闭）
│   │   ├── scheduler.py       周期任务（心跳检测、队列告警、令牌清理、KPI 快照）
│   │   ├── observability.py   trace id、结构化访问日志、Prometheus 指标
│   │   ├── ratelimit.py       令牌桶限流（读/写/登录三档）
│   │   ├── scoping.py         机构级行级数据隔离
│   │   └── ...                配置、数据库、统一响应、JWT+RBAC、SHA256 审计链
│   ├── models/                67 张表：资产/标签/模型/流水线/Agent/评测/合规/云边/注册/运营/系统/作业
│   ├── services/              业务与算法层（含 job_service 作业接入、experiment_service 实验编排）
│   └── api/v1/                15 个业务模块的 REST 接口
├── frontend/                  Node 静态服务 + API 反向代理 + 自包含控制台
├── scripts/                   自测脚本
└── data/                      院内本地数据目录（数据不出域）
```

### 算法服务（真实可算，非桩函数）

| 文件 | 内容 |
|---|---|
| `image_utils.py` | 光学密度、颜色去卷积（H&E 最小二乘解）、Reinhard 染色归一化、组织掩膜、核分割与形态学量（67 维图块特征） |
| `wsi_service.py` | 合成 WSI 金字塔（4 层倍率）+ 真实文件读取器、图块抽取、病灶掩膜、**中心级染色/扫描差异**、分层难度设计 |
| `encoder_service.py` | 可插拔图块编码器注册表 + **许可证硬门禁**（product 环境调用非商用权重直接拦截）+ 双源并行 |
| `mil_service.py` | 门控注意力 ABMIL（手写前向/反向/Adam）、Platt 标定（带步长控制的牛顿迭代）、置信度分级 |
| `evaluation_service.py` | AUROC / 敏感度 / 特异度 / PPV / NPV / ECE / Brier、Bootstrap 置信区间、按中心分组泛化衰减、MRMC 配对检验 |
| `agent_service.py` | 五智能体编排：分诊 → 导航（低倍到高倍逐级探查）→ 描述（形态学规则生成）→ 诊断（多轨迹投票）；**证据强制引用**、拒识机制、医生终审流转 |
| `edge_service.py` | FedAvg 联邦式增量微调（样本不出域，只出参数）、模型下发与回滚 |
| `registry_service.py` | 注册时间轴、里程碑、风险 2×2 矩阵、多中心试验入组 |
| `compliance_service.py` | 数据不出域校验、可解释性四件套、注册就绪度体检 |
| `ops_service.py` | 立项决策看板、团队编制、成本结构（仅相对比例）、KPI 快照 |
| `job_service.py` | 作业接入层：10 类作业 handler、提交/查询/取消/重试、待办中心聚合 |
| `experiment_service.py` | 实验编排：评测与 MRMC 对照（HTTP 同步入口与异步作业入口共用同一实现） |

---

## 四、设计文档章节 ↔ 代码模块对照

| 设计文档章节 | 代码模块 | 关键接口 |
|---|---|---|
| 摘要 / 第十一章 结论与立项建议 | `ops` | `/ops/dashboard`、`/ops/decision-board` |
| 第一章 项目背景与战略机会 | `ops`（政策/支付节点）、`registry/guidelines` | `/registry/guidelines` |
| 第二章 业内同类方案对标 | `agents/architecture`、`models` | `/agents/architecture` |
| 第三章 数据资产盘点与治理 | `assets`、`labels` | `/assets/overview`、`/labels/coverage` |
| 第四章 蓝天健康模型技术方案 | `models`、`pipeline` | `/models/encoders`、`/models/train` |
| 第五章 智慧医疗 Agent 设计 | `agents` | `/agents/run`、`/agents/sessions/{id}/detail` |
| 第六章 技术栈、算力与部署架构 | `edge` | `/edge/overview`、`/edge/federated-jobs/{id}/detail` |
| 第七章 合规与注册路径 | `compliance`、`registry` | `/compliance/readiness`、`/registry/timeline` |
| 第八章 实施路线图与里程碑 | `registry` | `/registry/milestones`、`/registry/timeline` |
| 第九章 投入产出与团队配置 | `ops` | `/ops/team-plan`、`/ops/cost-structure` |
| 第十章 风险与应对 | `registry` | `/registry/risks/board` |
| 附录 术语与口径 | 全模块 + `system/catalog` | `/system/catalog` |

---

## 五、四条不可妥协的设计约束

这四条不是代码风格问题，而是**决定了这个项目能不能注册、能不能回款**。

1. **许可证门禁是硬的，不是提示。**
   业内最强的病理开源权重（UNI2-h：CC-BY-NC-ND 4.0、Virchow2：CC-BY-NC、GigaPath：研究许可）
   都不可商用。`encoder_service.assert_commercial_usable()` 在 `product` 环境会直接抛出
   `LicenseViolation`，用非商用权重跑商业主线在代码层面就跑不通——避免它只在注册申报时才爆发（风险 R2）。
   商用主线锁定 Apache-2.0 的 Hibou 系列 + 自研 `sh-encoder-*`；非商用权重只允许在 `research` 环境做技术储备。

2. **数据不出域是运行时可验证的事实，不是一句承诺。**
   联邦任务详情接口每次都会计算 `sample_left_domain_count`，它必须恒为 0；
   每轮参与方记录里 `data_left_domain=false` 逐条可查。这是注册审评「数据可溯源」的运行证据。

3. **AI 不给最终诊断，只给可追溯的依据。**
   每条结论都必须绑定具体区域坐标（`AgentEvidence.spatial_bbox`）或外部引用，
   未达证据阈值的描述不生成；最终诊断只能由医生终审接口写入。
   低置信度/能力越界/轨迹不一致一律**拒识转人工**，拒识原因必须落库可查。

4. **审计链是 SHA256 哈希链，写操作强制留痕。**
   `record_hash = SHA256(prev_hash || canonical_json(payload))`，
   `/compliance/audit-chain/verify` 可随时校验全链完整性。

---

## 六、演示数据的诚实边界

- **切片是合成的，算法链路是真的。** 仓库不含真实病理影像与模型权重（合规与体积原因）。
  合成 WSI 由 `wsi_service.SyntheticWSIReader` 确定性生成，包含 4 层倍率金字塔、
  中心级染色差异、分层难度（部分阳性样本刻意做成小灶/反应性增生难例），
  因此特征提取、ABMIL 训练、注意力证据、标定、评测、联邦聚合全部真实执行。
- **指标是真实的算法输出，不是写死的漂亮数字。** 例如：
  院内 AUROC 与外部验证 AUROC 会出现可观测的衰减（对应风险 R3）；
  MRMC 对照会诚实地给出「尚未证明优于人工，p 值不显著」；
  AUROC 恒为 1.0 的玩具问题被刻意避免。
- **金额口径。** 成本只保存相对结构比例，系统刻意不落任何绝对金额，
  避免本地倒推的数字被当成预算口径。真实预算需按公司口径单独测算。

---

## 七、接入真实数据与模型

1. **真实切片**：`Slide.file_path` 指向真实 WSI（支持读取器扩展），
   `wsi_service.open_slide()` 会自动选择 `FileWSIReader` 而非合成读取器。
2. **真实编码器**：在 `encoder_service.py` 注册表中新增一个 `EncoderSpec`
   （填写 `license_name` / `commercial_usable` / `is_self_developed`），
   实现 `encode_tiles()` 即可；ONNX Runtime 与 PyTorch 后端均可。
3. **切换数据库**：设 `SMARTHEALTH_DATABASE_URL` 指向 PostgreSQL / 达梦即可，
   启动时会自动补齐缺失列。
