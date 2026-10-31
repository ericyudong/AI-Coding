#!/usr/bin/env bash
# SmartHealth CI 统一入口：把「跑哪些检查」固化成一个脚本，而不是散落在各家 CI 的 YAML 里。
#
# 为什么这样设计：
# 流水线配置（GitHub Actions / GitLab CI / Jenkins / CNB）语法各不相同，但**要做的事**
# 是一样的。把检查项写进 YAML，换一个 CI 系统就得重写一遍，而且本地无法复现 ——
# 于是"本地跑过了，CI 上挂了"变成常态。
# 这里让脚本成为唯一事实来源：YAML 只是 `bash scripts/ci.sh <profile>` 的一层薄壳，
# 任何人、任何机器、任何 CI 都能用同一条命令得到同样的结论。
#
# 三个 profile（名字对应用户在什么阶段关心什么）：
#
#   fast     —— 每次 push / PR。纯 SQLite，零外部服务，几分钟内出结果。
#               覆盖：代码可导入、迁移可幂等、接口契约、前端字段契约、PG 方言可编译。
#
#   staging  —— 主干合并 / 预发部署。**必须有 PostgreSQL + Redis**。
#               这一档的价值在于：真正跑一遍生产形态 —— PG 的 SKIP LOCKED 领取、
#               Redis 分布式锁、多进程 Worker 并发、SSE 实时通道。
#               上面这些在 fast 档是**测不到**的（SQLite 无 SKIP LOCKED、无 Redis）。
#
#   release  —— 打 tag / 上线门禁。在 staging 之上再加真实数据与真实推理：
#               真实金字塔 TIFF 的逐像素读取、真实 ONNX 推理、权重治理与许可门禁，
#               并以 --fail-on-warn 作为最严格的放行条件。
#
# 用法：
#   bash scripts/ci.sh fast
#   SMARTHEALTH_DATABASE_URL=postgresql+psycopg://u:p@h:5432/db \
#   SMARTHEALTH_REDIS_URL=redis://h:6379/0 \
#   bash scripts/ci.sh release
#
# 实测耗时（本机，8 核 CPU、无 GPU）—— 决定把它放在哪个触发点上：
#   fast    ≈ 6 分钟，其中「装载演示数据」独占约 5 分钟，其余检查约 1 分钟
#   staging ≈ 10 分钟（含多进程与长连接测试）
#   release ≈ 13 分钟（再加真实切片生成与 ONNX 导出/推理）
#   若嫌 fast 太慢，可设 CI_SEED_SKIP_MODEL=1 把种子压到约 1 分钟
#   （代价：依赖模型产物的用例会被标记为"跳过"，不能作为完整结论）
#
# 环境变量：
#   PYTHON               指定解释器（默认 python；WorkBuddy 环境可指向内置解释器）
#   CI_SKIP_INSTALL      设为 1 时跳过依赖安装（依赖已由镜像/缓存准备好）
#   CI_SEED_MODE         种子模式：quick（默认）| full
#   CI_SEED_SKIP_MODEL   设为 1 时不装载训练/推理/评测产物（冒烟档，见上）
#   CI_KEEP_DB           设为 1 时保留 fast 档的临时库，便于事后排查

set -uo pipefail

PROFILE="${1:-fast}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON="${PYTHON:-python}"
CI_SEED_MODE="${CI_SEED_MODE:-quick}"

# seed 的参数数组：显式用数组而不是拼字符串，避免空参数被当成一个空字符串传给 argparse。
SEED_ARGS=(--reset "--$CI_SEED_MODE")
if [ "${CI_SEED_SKIP_MODEL:-0}" = "1" ]; then
  SEED_ARGS+=(--skip-model)
fi
# 是否具备"模型产物"（训练/推理/评测/Agent 会话）——决定哪些用例有意义
SEED_HAS_MODEL=1
if [ "${CI_SEED_SKIP_MODEL:-0}" = "1" ]; then
  SEED_HAS_MODEL=0
fi

# 「按配置声明的跳过」与「因上游失败而被迫跳过」是两回事：
#   - 声明的跳过（冒烟档）：操作者主动缩小范围，覆盖到的部分全绿就应当**放行**，
#     否则冒烟档在流水线里永远是红的，等于没人会用。
#   - 被迫的跳过：说明前面的步骤挂了，必须拦住，否则会把真问题放过去。
# 两类都打印出来，但只有后者影响退出码。
DECLARED_SKIPS=0
if [ "$SEED_HAS_MODEL" = "0" ]; then
  DECLARED_SKIPS=1
fi

# ---------------------------------------------------------------- 输出
if [ -t 1 ]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_RED=$'\033[31m'
  C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_BLUE=$'\033[36m'
else
  # CI 里没有 TTY：务必不要输出 ANSI 转义序列，否则日志文件里全是乱码，
  # 而且会让 `grep` 匹配失败（这是"CI 脚本本地好看、线上诡异"的常见原因）。
  C_RESET=""; C_BOLD=""; C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""
fi

STEP_NO=0
FAILED_STEPS=()
SKIPPED_STEPS=()
STEP_LOG_DIR="$(mktemp -d 2>/dev/null || echo "${TMPDIR:-/tmp}/smarthealth-ci")"
mkdir -p "$STEP_LOG_DIR"

banner() {
  echo
  echo "${C_BOLD}────────────────────────────────────────────────────────────────${C_RESET}"
  echo "${C_BOLD}  $*${C_RESET}"
  echo "${C_BOLD}────────────────────────────────────────────────────────────────${C_RESET}"
}

# 执行一步并把输出同时写到控制台与日志文件。
# 失败时**不立刻退出**：CI 里最浪费时间的是"修一个错、重跑一次、又发现下一个错"。
# 所以这里跑完全部步骤，最后统一汇总，一次就能看到所有问题。
step() {
  local name="$1"; shift
  STEP_NO=$((STEP_NO + 1))
  local log="$STEP_LOG_DIR/$(printf '%02d' "$STEP_NO")_$(echo "$name" | tr ' /' '__').log"
  echo
  echo "${C_BLUE}[$STEP_NO] $name${C_RESET}"
  local start
  start=$(date +%s)
  if "$@" >"$log" 2>&1; then
    local dur=$(( $(date +%s) - start ))
    echo "  ${C_GREEN}✓ 通过${C_RESET}（${dur}s）"
    # 通过时只回显关键行，避免 CI 日志被淹没；完整输出留在日志文件里
    grep -E "通过 [0-9]+|DOCTOR_SUMMARY|全绿|结论|项：OK" "$log" | tail -3 | sed 's/^/    /' || true
    return 0
  else
    local code=$?
    local dur=$(( $(date +%s) - start ))
    echo "  ${C_RED}✗ 失败${C_RESET}（exit=$code，${dur}s）"
    echo "  ${C_YELLOW}失败详情（完整输出见 $log）：${C_RESET}"
    grep -E "^\[FAIL\]|FAIL|失败|Error|Traceback|DOCTOR_SUMMARY|\[WARN\]" "$log" | head -25 | sed 's/^/    /' || true
    tail -15 "$log" | sed 's/^/    | /'
    FAILED_STEPS+=("$name  ->  $log")
    return 1
  fi
}

# 跳过一步：用于"上游失败导致本步无法有意义地执行"的情况。
#
# 为什么值得区分"失败"与"跳过"：如果 seed 挂了，后面三个依赖演示数据的用例都会挂，
# 报告里就是"4 个失败"—— 看起来像四处崩坏，实际只有一个根因。
# 这会直接误导排查方向（有人会去逐个查那三个用例），也让"到底修了几个问题"失去意义。
skip() {
  local name="$1" reason="$2"
  STEP_NO=$((STEP_NO + 1))
  echo
  echo "${C_BLUE}[$STEP_NO] $name${C_RESET}"
  echo "  ${C_YELLOW}⊘ 跳过${C_RESET}：$reason"
  SKIPPED_STEPS+=("$name  （$reason）")
  return 0
}

# ---------------------------------------------------------------- 环境准备
banner "SmartHealth CI · profile=$PROFILE · python=$($PYTHON --version 2>&1)"

install_deps() {
  if [ "${CI_SKIP_INSTALL:-0}" = "1" ]; then
    echo "CI_SKIP_INSTALL=1，跳过依赖安装"
    return 0
  fi
  "$PYTHON" -m pip install --quiet --disable-pip-version-check -r requirements.txt
}

case "$PROFILE" in
  fast)
    # fast 档要能在**任何**机器上跑：显式使用项目内临时 SQLite 库，
    # 不受外部 PG/Redis 环境变量影响（否则同一份代码在不同机器上结论不同）。
    #
    # 路径**必须交给 Python 算**，不能在 shell 里拼字符串：
    # Git Bash / MSYS 的 `pwd` 返回的是 `/c/Code_Space/...` 这种 POSIX 形式，
    # 直接拼成 URL 会得到 `sqlite:////c/Code_Space/...`（四个斜杠的非法路径），
    # 表现是 `unable to open database file` —— 而且只在 Windows 上出现。
    # Python 的 Path.cwd() 拿到的是真实 Windows 路径，as_posix() 后即为正确形式。
    export SMARTHEALTH_DATABASE_URL="$("$PYTHON" -c "
from pathlib import Path
p = (Path.cwd() / 'data' / 'ci_fast.db').resolve()
p.parent.mkdir(parents=True, exist_ok=True)
print('sqlite:///' + p.as_posix())
")"
    if [ -z "$SMARTHEALTH_DATABASE_URL" ]; then
      echo "${C_RED}错误：无法确定 CI 数据库路径（Python 未能解析项目目录）${C_RESET}"
      exit 2
    fi
    CI_FAST_DB="$("$PYTHON" -c "
from pathlib import Path
print((Path.cwd() / 'data' / 'ci_fast.db').resolve())
")"
    unset SMARTHEALTH_REDIS_URL || true
    ;;
  staging|release)
    if [ -z "${SMARTHEALTH_DATABASE_URL:-}" ]; then
      echo "${C_RED}错误：profile=$PROFILE 需要 PostgreSQL，请设置 SMARTHEALTH_DATABASE_URL${C_RESET}"
      echo "  例：postgresql+psycopg://smarthealth:pwd@127.0.0.1:5432/smarthealth_ci"
      echo
      echo "  为什么强制要求：staging/release 的意义就是验证**生产形态**。"
      echo "  用 SQLite 跑这一档，SKIP LOCKED 领取、真实并发写、Redis 分布式锁全都没被覆盖 ——"
      echo "  那样即使全绿也不能作为上线依据。"
      exit 2
    fi
    if [ -z "${SMARTHEALTH_REDIS_URL:-}" ]; then
      echo "${C_RED}错误：profile=$PROFILE 需要 Redis，请设置 SMARTHEALTH_REDIS_URL${C_RESET}"
      echo "  例：redis://127.0.0.1:6379/0"
      exit 2
    fi
    ;;
  *)
    echo "未知 profile：$PROFILE（可选：fast | staging | release）"
    exit 2
    ;;
esac

# 上线门禁必须按生产环境校验非商用权重
if [ "$PROFILE" = "release" ]; then
  export SMARTHEALTH_DEPLOYMENT_ENV="${SMARTHEALTH_DEPLOYMENT_ENV:-product}"
fi

echo "  profile      : $PROFILE"
echo "  database     : ${SMARTHEALTH_DATABASE_URL%%\?*}"
echo "  redis        : ${SMARTHEALTH_REDIS_URL:-（未配置）}"
echo "  部署环境      : ${SMARTHEALTH_DEPLOYMENT_ENV:-research}"
echo "  种子模式      : $CI_SEED_MODE"

# ---------------------------------------------------------------- 通用步骤
case "$PROFILE" in
  fast)
    step "依赖安装" install_deps
    step "数据库迁移可执行（幂等）" "$PYTHON" -c "
import sys
sys.path.insert(0, '.')
from app.core.database import init_db
first = init_db()
second = init_db()
applied_first, applied_second = len(first['applied']), len(second['applied'])
print(f'首次应用 {applied_first} 条，再次应用 {applied_second} 条')
assert applied_second == 0, f'迁移不幂等：第二次仍应用了 {applied_second} 条'
print('迁移幂等性校验通过')
"
    if step "装载演示数据（$CI_SEED_MODE${CI_SEED_SKIP_MODEL:+ / 跳过模型产物}）" \
         "$PYTHON" -m app.seed "${SEED_ARGS[@]}"; then
      SEED_OK=1
    else
      SEED_OK=0
    fi
    step "部署预检（doctor）" "$PYTHON" scripts/doctor.py --ci --skip-lock-selftest
    step "PostgreSQL 方言编译校验" "$PYTHON" scripts/check_pg_dialect.py
    # 这两个用例都会断言"Agent 会话/预测/评测结果非空"，因此必须要有模型产物。
    # 冒烟档（CI_SEED_SKIP_MODEL=1）下把它们标为跳过，而不是让它们报一堆假失败。
    if [ "$SEED_OK" = "1" ] && [ "$SEED_HAS_MODEL" = "1" ]; then
      step "后端接口自测" "$PYTHON" scripts/selftest_api.py
      step "前端字段契约校验" "$PYTHON" scripts/selftest_frontend.py
    elif [ "$SEED_OK" != "1" ]; then
      skip "后端接口自测" "演示数据装载失败，缺少 admin 账号与切片数据"
      skip "前端字段契约校验" "演示数据装载失败"
    else
      skip "后端接口自测" "冒烟档未装载模型产物（CI_SEED_SKIP_MODEL=1），断言依赖训练/推理结果"
      skip "前端字段契约校验" "冒烟档未装载模型产物"
    fi
    ;;

  staging)
    step "依赖安装" install_deps
    step "部署预检（PG + Redis 门禁）" "$PYTHON" scripts/doctor.py --ci --init-db --require-postgres --require-redis
    if step "装载演示数据（$CI_SEED_MODE）" "$PYTHON" -m app.seed "${SEED_ARGS[@]}"; then
      SEED_OK=1
    else
      SEED_OK=0
    fi
    step "部署预检（数据装载后复检）" "$PYTHON" scripts/doctor.py --ci --require-postgres --require-redis
    if [ "$SEED_OK" = "1" ]; then
      step "后端接口自测（PG 路径）" "$PYTHON" scripts/selftest_api.py
      step "前端字段契约校验" "$PYTHON" scripts/selftest_frontend.py
      step "多进程 Worker 并发验证（真实进程 + PG）" "$PYTHON" scripts/selftest_multiprocess.py --processes 4 --jobs 16
      step "实时事件通道（SSE / WS / 降级通道）" "$PYTHON" scripts/selftest_stream.py
    else
      skip "后端接口自测（PG 路径）" "演示数据装载失败"
      skip "前端字段契约校验" "演示数据装载失败"
      skip "多进程 Worker 并发验证" "演示数据装载失败（无切片可投递）"
      skip "实时事件通道" "演示数据装载失败"
    fi
    ;;

  release)
    step "依赖安装" install_deps
    step "部署预检（严格门禁：PG + Redis + 无 WARN）" "$PYTHON" scripts/doctor.py --ci --init-db --require-postgres --require-redis
    if step "装载演示数据（$CI_SEED_MODE）" "$PYTHON" -m app.seed "${SEED_ARGS[@]}"; then
      SEED_OK=1
    else
      SEED_OK=0
    fi
    # 样例切片与参照权重不依赖演示数据，即使 seed 失败也照跑 ——
    # 它们验证的是"读取与推理链路"，属于独立的能力面。
    step "生成真实金字塔切片样例" "$PYTHON" scripts/make_sample_wsi.py --size 2048 --levels 4
    step "导出自研参照 ONNX 模型" "$PYTHON" scripts/model_registry.py export-reference
    step "权重清单完整性校验" "$PYTHON" scripts/model_registry.py verify --all
    step "许可体检（商用主线准入）" "$PYTHON" scripts/model_registry.py license-audit
    step "PostgreSQL 方言编译校验" "$PYTHON" scripts/check_pg_dialect.py
    step "真实 WSI 读取链路（逐像素比对）" "$PYTHON" scripts/selftest_wsi.py
    step "ONNX 真实推理与权重治理" "$PYTHON" scripts/selftest_onnx.py
    if [ "$SEED_OK" = "1" ]; then
      step "后端接口自测" "$PYTHON" scripts/selftest_api.py
      step "前端字段契约校验" "$PYTHON" scripts/selftest_frontend.py
      step "多进程 Worker 并发验证" "$PYTHON" scripts/selftest_multiprocess.py --processes 4 --jobs 16
      step "实时事件通道（SSE / WS / 降级通道）" "$PYTHON" scripts/selftest_stream.py
    else
      skip "后端接口自测" "演示数据装载失败"
      skip "前端字段契约校验" "演示数据装载失败"
      skip "多进程 Worker 并发验证" "演示数据装载失败"
      skip "实时事件通道" "演示数据装载失败"
    fi
    # 最严格的一关放在最后：前面所有功能都通过后，再要求"零 WARN"。
    # 这样报出来的 WARN 是"唯一阻止上线的原因"，不会被功能失败淹没。
    step "上线门禁终检（--fail-on-warn）" "$PYTHON" scripts/doctor.py --ci --require-postgres --require-redis --fail-on-warn
    ;;
esac

# ---------------------------------------------------------------- 汇总
banner "CI 结果汇总 · profile=$PROFILE"
if [ ${#FAILED_STEPS[@]} -eq 0 ]; then
  if [ ${#SKIPPED_STEPS[@]} -gt 0 ] && [ "$DECLARED_SKIPS" != "1" ]; then
    # 有跳过但配置上没声明要缩小范围 —— 异常情形，不能放行
    echo "  ${C_YELLOW}注意：有 ${#SKIPPED_STEPS[@]} 个步骤被跳过，**不能视为全通过**。${C_RESET}"
    for item in "${SKIPPED_STEPS[@]}"; do
      echo "    ${C_YELLOW}⊘${C_RESET} $item"
    done
    echo
    echo "CI_SUMMARY profile=$PROFILE steps=$STEP_NO failed=0 skipped=${#SKIPPED_STEPS[@]} result=fail_undeclared_skip"
    exit 1
  fi
  if [ ${#SKIPPED_STEPS[@]} -gt 0 ]; then
    echo "  ${C_GREEN}已执行的 $((STEP_NO - ${#SKIPPED_STEPS[@]})) 个步骤全部通过${C_RESET}"
    echo "  ${C_YELLOW}以下 ${#SKIPPED_STEPS[@]} 项按配置跳过（不是缺陷，但覆盖范围不完整）：${C_RESET}"
    for item in "${SKIPPED_STEPS[@]}"; do
      echo "    ${C_YELLOW}⊘${C_RESET} $item"
    done
    echo "CI_SUMMARY profile=$PROFILE steps=$STEP_NO failed=0 skipped=${#SKIPPED_STEPS[@]} result=pass_with_declared_skips"
    exit 0
  fi
  echo "  ${C_GREEN}${C_BOLD}全部 $STEP_NO 个步骤通过${C_RESET}"
  echo
  if [ "$PROFILE" = "release" ]; then
    echo "  → 该构建满足上线门禁条件（PostgreSQL + Redis + 零 WARN + 真实数据/推理全通过）"
  elif [ "$PROFILE" = "staging" ]; then
    echo "  → 生产形态（PG + Redis + 多进程 + 实时通道）验证通过"
  else
    echo "  → 注意：fast 档使用 SQLite，**未**覆盖 SKIP LOCKED 与 Redis 分布式锁；"
    echo "     上线前必须以 staging / release 档再跑一次。"
  fi
  echo "CI_SUMMARY profile=$PROFILE steps=$STEP_NO failed=0 skipped=0 result=pass"
  echo "  详细日志：$STEP_LOG_DIR"
  if [ "$PROFILE" = "fast" ] && [ "${CI_KEEP_DB:-0}" != "1" ] && [ -n "${CI_FAST_DB:-}" ]; then
    rm -f "${CI_FAST_DB}" "${CI_FAST_DB}-wal" "${CI_FAST_DB}-shm" 2>/dev/null || true
    echo "  已清理 CI 临时库（设 CI_KEEP_DB=1 可保留以便排查）"
  fi
  exit 0
fi

echo "  ${C_RED}${C_BOLD}失败的步骤（共 ${#FAILED_STEPS[@]} 个）：${C_RESET}"
for item in "${FAILED_STEPS[@]}"; do
  echo "    ${C_RED}✗${C_RESET} $item"
done
if [ ${#SKIPPED_STEPS[@]} -gt 0 ]; then
  echo
  echo "  ${C_YELLOW}被跳过的步骤（共 ${#SKIPPED_STEPS[@]} 个，均为上游失败的连带影响，不是独立缺陷）：${C_RESET}"
  for item in "${SKIPPED_STEPS[@]}"; do
    echo "    ${C_YELLOW}⊘${C_RESET} $item"
  done
  echo "  → 先修上面列出的失败项，被跳过的步骤会自动恢复执行。"
fi
echo
echo "CI_SUMMARY profile=$PROFILE steps=$STEP_NO failed=${#FAILED_STEPS[@]} skipped=${#SKIPPED_STEPS[@]} result=fail"
echo "  提示：每个步骤的完整输出都在上面列出的日志文件里；"
echo "        本地复现单步更快的做法是直接执行对应命令（见日志首行）。"
echo "  日志目录：$STEP_LOG_DIR"
exit 1
