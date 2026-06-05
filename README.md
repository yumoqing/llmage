# llmage 模块开发文档

## 模块概述

llmage (LLM Manager & Engine) 是 Hermes Agent 平台的**大语言模型管理与推理模块**，负责 LLM 的全生命周期管理：模型注册、分类展示、推理调度、用量追踪与计费。

与 uapi 模块的配合关系：**llmage 负责模型的业务层**（模型目录、展示、推理调度、计费），**uapi 负责配置层的 API 对接**（将第三方 LLM API 配置为可调用的端点）。llmage 中的每个模型（llm 表记录）通过 `upappid` + `apiname` 关联到 uapi 的 API 配置，从而实现零代码接入新模型。

核心职责：
- 模型管理：模型注册、分类（catelog）、供应商（provider）管理
- 推理引擎：流式/同步/异步三种推理模式，自动路由
- 用量追踪：每次调用记录 token 用量、响应时间、用户信息
- 计费系统：按定价程序（pricing program）计算费用，后台异步记账
- 前端展示：按目录/供应商分类展示模型卡片，点击即推理对话
- 异步任务：视频生成等长任务的提交、轮询、状态查询

---

## 目录结构

```
llmage/
├── pyproject.toml              # 构建配置
├── llmage/                     # Python 源码包
│   ├── __init__.py             # 空
│   ├── init.py                 # 模块初始化，注册函数到 ServerEnv + 后台记账任务
│   ├── llmclient.py            # 推理引擎核心：uapi_request / sync_uapi_request / async_uapi_request
│   ├── syncinference.py        # 同步推理模式
│   ├── asyncinference.py       # 异步推理模式 + 任务状态轮询
│   ├── accounting.py           # 计费与记账：余额检查、充电、后台异步记账
│   ├── utils.py                # 工具函数：BufferedLLMs 缓存、查询订单、价格计算等
│   ├── callback.py             # 回调处理
│   ├── messages.py             # 消息格式化
│   ├── keling.py               # 可灵（Keling）视频模型 token 管理
│   └── jimeng.py               # 即梦（Jimeng）图像模型认证
├── models/                     # 表定义（xlsx 格式）
│   ├── llm.xlsx                # 模型定义
│   ├── llmusage.xlsx           # 模型调用记录
│   ├── llmcatelog.xlsx         # 模型目录
│   └── historyformat.xlsx      # 历史对话格式
├── wwwroot/                    # Web 前端资源
│   ├── menu.ui                 # 菜单
│   ├── show_llms.ui            # 按目录展示模型卡片
│   ├── show_llms_by_providers.ui  # 按供应商展示模型
│   ├── show_same_catelog_llm.ui   # 同目录模型展示
│   ├── llm_dialog.ui           # 模型对话窗口（LlmIO 控件）
│   ├── llminference.dspy       # 推理入口（调用 inference_generator）
│   ├── list_paging_catelog_llms.dspy  # 分页目录模型列表
│   ├── list_catelog_models.dspy     # 目录模型列表
│   ├── get_type_llms.dspy      # 按类型获取模型
│   ├── model_estimate.dspy     # 费用预估
│   ├── query_price.dspy        # 价格查询
│   ├── llmcost.dspy            # 费用统计
│   ├── llmcheck.dspy           # 模型检查
│   ├── llmaccounting.dspy      # 手动记账触发
│   ├── vidu_inference.dspy     # Vidu 视频推理入口
│   ├── vidu_callback.dspy      # Vidu 回调处理
│   ├── get_asynctask_status.dspy    # 异步任务状态查询
│   ├── get_my_asynctasks.dspy       # 我的异步任务列表
│   ├── grap_task_status.dspy        # 抓取任务状态
│   ├── tasks/index.dspy        # 任务管理入口
│   ├── openai/index.dspy       # OpenAI 兼容接口
│   ├── v1/chat/completions/index.dspy  # OpenAI v1 聊天接口
│   ├── t2t/index.dspy          # 文本到文本接口
│   └── video/index.dspy        # 视频生成接口
└── script/
    └── perms.json              # RBAC 权限配置
```

---

## 数据库表结构

### 表关系

```
llmcatelog (模型目录) ──1:N──> llm (模型)
llm (模型) ──N:1──> upapp (上位系统, 通过 uapi 模块)
llm (模型) ──1:N──> llmusage (调用记录)
```

### 核心表说明

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| **llmcatelog** | 模型目录分类 | id, name |
| **llm** | 模型定义 | id, name, model, providerid, ownerid, upappid, apiname, llmcatelogid, stream（同步/异步/流式）, ppid（定价程序id）, callbackurl, enabled_date, expired_date, input_fields |
| **llmusage** | 模型调用记录 | id, llmid, userid, userorgid, usages(token用量), status(SUCCEEDED/FAILED), amount(金额), cost(成本), use_time, accounting_status(created/accounted/failed), taskid(异步任务id) |
| **historyformat** | 历史对话格式 | id, name, format |

---

## 架构设计：llmage + uapi 协同

```
用户点击模型卡片
       │
       ▼
  llm_dialog.ui ── 显示 LlmIO 对话控件
       │
       ▼
  llminference.dspy ── 推理入口
       │
       ▼
  inference_generator() ── 推理引擎核心（llmclient.py）
       │
       ├── 判断 llm.stream:
       │
       ├── 'async' ──→ async_uapi_request() ── 提交任务 + 后台轮询状态
       │                     │
       │                     └── 通过 uapi 的 UpAppApi 调用远端 API
       │
       ├── False ──→ sync_uapi_request() ─── 一次性同步调用
       │                     │
       │                     └── 通过 uapi 的 UpAppApi 调用远端 API
       │
       └── True ──→ uapi_request() ────── 流式调用（SSE）
                             │
                             └── 通过 uapi 的 UpAppApi stream_linify()
```

**关键连接点**：llm 表中的 `upappid` + `apiname` 指向 uapi 模块中配置的外部 API。uapi 负责：
- 管理 upapp（上位系统）的 baseurl、认证密钥
- 管理 uapi（API 定义）的 httpmethod、path、headers、模板渲染
- 提供 UpAppApi 类进行实际 HTTP 调用

llmage 负责：
- 模型业务逻辑（分类、展示、选择）
- 推理调度（选择同步/异步/流式模式）
- 调用记录追踪（llmusage 表）
- 计费记账（accounting）

---

## Python API

### 模块初始化

```python
def load_llmage():
    env = ServerEnv()
    env.llm_query_orders = llm_query_orders
    env.read_webpath = read_webpath
    env.get_llm_by_model = get_llm_by_model
    env.llm_charging = llm_charging
    env.get_accounting_llmusages = get_accounting_llmusages
    env.llm_accounting = llm_accounting
    env.get_today_asynctask_list = get_today_asynctask_list
    env.get_asynctask_status = get_asynctask_status
    env.query_task_status = query_task_status
    env.get_llm = get_llm
    env.inference = inference
    env.inference_generator = inference_generator
    env.get_llms_by_catelog = get_llms_by_catelog
    env.get_llmcatelogs = get_llmcatelogs
    env.checkCustomerBalance = checkCustomerBalance
    env.get_llmproviders = get_llmproviders
    env.get_llms_sort_by_provider = get_llms_sort_by_provider
    env.keling_token = keling_token
    env.llm_query_price = llm_query_price
    env.jimeng_auth_headers = jimeng_auth_headers

    # 启动后台记账任务
    add_cleanupctx(start_backend)  # backend_accounting() 每10秒轮询
```

其他模块的 `.dspy` 文件可通过 `globals()` 直接使用这些函数。

### 推理引擎（llmclient.py）

三种推理模式：

#### 1. 流式推理（uapi_request）

适用于支持 SSE 流式返回的 LLM API（如 GPT-4、Claude）。

```python
async for line in uapi_request(request, llm, callerid, callerorgid, params_kw):
    yield line  # 每行是一个 JSON，包含 content/reasoning_content/usage
```

**输出格式**：
```json
{"content": "你好", "llmusageid": "xxx"}
{"reasoning_content": "让我想想...", "llmusageid": "xxx"}
{"usage": {"prompt_tokens": 10, "completion_tokens": 20}, "llmusageid": "xxx"}
```

#### 2. 同步推理（sync_uapi_request）

适用于一次性返回完整结果的 API。

```python
result = await sync_uapi_request(request, llm, callerid, callerorgid, params_kw)
# result 是 JSON 字符串
```

#### 3. 异步推理（async_uapi_request）

适用于视频生成等耗时任务。提交后立即返回 taskid，后台轮询状态。

```python
result = await async_uapi_request(request, llm, callerid, callerorgid, params_kw)
# result: {"taskid": "xxx", "status": "PENDING"}
# 后台自动通过 query_task_status() 轮询，更新 llmusage 表
```

### inference / inference_generator 入口

```python
# 在 .dspy 中使用（流式）
async def handle(request, params_kw=None):
    async for line in inference_generator(request, params_kw=params_kw):
        yield line

# 或者直接使用 inference（自动包装为流式响应）
result = await inference(request, params_kw=params_kw)
```

**参数要求**：
- `params_kw.llmid`: 模型 ID（必填）
- `params_kw.model`: 模型名称（可选，自动从 llm 表填充）
- `params_kw.transno`: 交易号（可选，自动生成）
- `params_kw.stream`: 是否流式（可选）

### 模型查询

```python
# 通过 llmid 获取模型信息（带内存缓存）
llm = await get_llm(llmid)

# 按目录获取模型列表
llms_by_catelog = await get_llms_by_catelog()
# 返回: [{'catelogid': 'x', 'catelogname': '文本', 'llms': [...]}]

# 按供应商获取模型列表
llms_by_provider = await get_llms_sort_by_provider()

# 获取所有目录
catelogs = await get_llmcatelogs()

# 获取所有供应商
providers = await get_llmproviders()
```

### 计费与记账（accounting.py）

```python
# 检查用户余额是否足够使用某模型
has_balance = await checkCustomerBalance(llmid, userorgid)

# 计算费用（通过定价程序）
chargings = await llm_charging(ppid, llmusage)
# 返回: DictObject(original_amount, amount, cost)

# 价格查询
prices = await llm_query_price(llmid, config_data)

# 后台记账（由 start_backend 自动启动，每10秒轮询）
# 处理 llmusage 中 accounting_status='created' 的记录
await backend_accounting()

# 手动记账
await llm_accounting(llmusage)
```

### 异步任务管理（asyncinference.py）

```python
# 查询异步任务状态
status = await get_asynctask_status(request, taskid)
# 返回: {'taskid': 'xxx', 'status': 'SUCCEEDED'|'FAILED'|'PENDING', ...}

# 获取今天的异步任务列表
tasks = await get_today_asynctask_list(userid)

# 手动轮询任务状态（onetime=True 只查一次）
await query_task_status(request, luid, onetime=False)
```

### 历史推理记录查询

`GET /llmage/api/get_inference_history.dspy`

跨表（llmusage + llmusage_history）分页查询当前用户的推理历史，按时间倒序返回，默认每页 10 条。自动通过 FileStorage 读取 ioinfo 文件内容，返回实际输入输出。

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码，默认 1 |
| pagerows | int | 否 | 每页条数，默认 10 |
| llmcatelogid | str | 否 | 按模型分类 ID 过滤，仅返回该分类下模型的记录 |

**返回字段**：

| 字段 | 说明 |
|------|------|
| success | 是否成功 |
| total | 两表合计总记录数 |
| page | 当前页码 |
| page_size | 每页条数（默认 10，可通过 pagerows 参数指定） |
| rows | 记录列表 |

**rows 中每条记录**：

| 字段 | 说明 |
|------|------|
| id | 记录 ID |
| llmid | 模型 ID |
| use_date | 使用日期 |
| use_time | 使用时间（排序依据） |
| userid | 用户 ID |
| usages | token 用量（JSON 对象） |
| status | 调用状态（ok/failed 等） |
| ioinfo | 原始 webpath |
| io_content | 解析后的输入输出内容，包含 input 和 output；读取失败时为 null |
| amount | 费用金额 |
| userorgid | 组织 ID |
| accounting_status | 记账状态 |

**返回示例**：

```json
{
  "success": true,
  "rows": [
    {
      "id": "abc123",
      "llmid": "model001",
      "use_date": "2026-06-05",
      "use_time": "2026-06-05 12:30:00",
      "userid": "user001",
      "usages": {"total_tokens": 1000, "prompt_tokens": 800, "completion_tokens": 200},
      "status": "ok",
      "io_content": {"input": [...], "output": [...]},
      "amount": 0.05,
      "accounting_status": "accounted"
    }
  ],
  "total": 156,
  "page": 1,
  "page_size": 50
}
```

**权限**：logined（所有已登录用户），仅返回当前登录用户自己的记录。

---

## 前端页面

### show_llms.ui — 模型展示

按目录（catelog）分组展示模型卡片，点击卡片弹出 llm_dialog.ui 对话窗口。

```jinja2
{% for cate in get_llms_by_catelog() %}
    {% for llm in cate.llms %}
        模型卡片 → click → urlwidget → llm_dialog.ui?id={{llm.id}}
    {% endfor %}
{% endfor %}
```

### llm_dialog.ui — 模型对话窗口

LlmIO 控件，支持流式输出、多模型切换、知识库选择等。

```jinja2
{% if checkCustomerBalance(params_kw.id, userorgid) %}
{% set llm = get_llm(params_kw.id) %}
    LlmIO 控件 → 推理地址: /llmage/llminference.dspy
{% endif %}
```

### llminference.dspy — 推理入口

```python
# 接收 params_kw（包含 llmid、prompt 等参数）
# 调用 inference_generator 进行推理
async for line in inference_generator(request, params_kw=params_kw):
    yield line
```

### OpenAI 兼容接口

- `/llmage/openai/` — OpenAI 兼容的接口入口
- `/llmage/v1/chat/completions/` — 标准 OpenAI chat completions 接口

---

## 关键设计要点

1. **llm ↔ uapi 桥接**：llm 表通过 `upappid` + `apiname` 关联到 uapi 的 API 配置，实现零代码接入新模型
2. **BufferedLLMs 缓存**：模型定义按日期缓存，避免每次查询数据库；跨天自动失效
3. **三种推理模式**：流式（SSE）、同步（一次性返回）、异步（提交+轮询），根据 `llm.stream` 字段自动选择
4. **异步任务轮询**：后台自动轮询任务状态（`query_task_status`），支持多 API 名称轮询（`query_apiname` 逗号分隔）
5. **IO 持久化**：每次调用的输入输出以 JSON 文件存储（通过 FileStorage），llmusage 表只存 webpath
6. **计费延迟**：联机不调账，标记 `accounting_status='created'`，后台记账任务每10秒批量处理
7. **API Key 保护**：异常信息中的 Bearer token 会被 `erase_apikey()` 替换为 XXXXXXXX
8. **供应商认证**：可灵（keling_token）和即梦（jimeng_auth_headers）有专用的认证函数

---

## 依赖关系

```
llmage
├── sqlor          # 数据库 ORM
├── apppublic      # 工具库（日志、唯一ID、时间工具等）
├── ahserver       # Web 服务器框架
├── uapi           # 外部 API 网关（推理调用依赖 UpAppApi）
└── accounting     # 计费模块（consume_accounting, getCustomerBalance）
```

---

## 开发注意事项

1. **llm.stream 字段**：控制推理模式 — `'async'` 为异步任务、`False` 为同步、`True` 为流式
2. **llm 表关联链**：llm → upapp → uapi + uapiio，新增模型需在 uapi 模块中先配置好 API 定义。模型能力字段（apiname, query_apiname, query_period, ppid）已拆分到 llm_api_map 表。
3. **input_fields**：模型的输入字段定义存储在 uapiio 表中，BufferedLLMs 加载时自动关联
4. **计费开关**：目前联机不调账（代码中已注释），所有 amount/cost 为 0，由后台任务统一处理
5. **异步任务 query_apiname**：支持多个 API 名称逗号分隔，逐个轮询直到状态变为 SUCCEEDED/FAILED
6. **query_period**：轮询间隔（秒），默认 30 秒，在 llm 表中配置
