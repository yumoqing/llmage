# llmage API 文档

Base Path: `/llmage/v1`

所有 API 端点需要 Bearer Token 认证（`logined` 权限）。

---

## POST /v1/chat/completions

文本生成接口，兼容 OpenAI 格式。

### 必填参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `model` | string | 模型名称，如 `"qwen3-max"` |
| `messages` 或 `prompt` | array / string | 对话消息数组或文本提示 |

### 可选参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `stream` | boolean | 是否启用流式输出 |
| `off_peak` | boolean | 是否使用非高峰时段 |
| `transno` | string | 交易流水号（不传则自动生成） |

### 请求示例

```json
{
    "model": "qwen3-max",
    "messages": [
        {"role": "user", "content": "Hello"}
    ],
    "stream": false
}
```

### 响应格式

**非流式响应:**

```json
{
    "id": "luid_xxx",
    "object": "chat.completion",
    "model": "qwen3-max",
    "choices": [{
        "index": 0,
        "message": {"role": "assistant", "content": "Hi there!"},
        "finish_reason": "stop"
    }],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
}
```

**流式响应 (SSE):**

```
data: {"choices": [{"delta": {"content": "Hi"}, "index": 0}]}
data: {"choices": [{"delta": {"content": " there!"}, "index": 0}]}
data: [DONE]
```

### 错误响应

| 状态码 | 说明 |
|--------|------|
| 400 | 缺少必填参数或模型不存在 |
| 403 | 未登录 |
| 429 | 账户余额不足 |

---

## POST /v1/video/generations

视频生成接口。

### 必填参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `model` | string | 模型名称，如 `"keling-2.1"` |
| `llmcatelogid` | string | 目录类型，如 `"文生视频"` / `"图生视频"` |
| `prompt` | string | 生成提示词 |

### 可选参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `image_url` | string | 图生视频时提供参考图 URL |
| `duration` | string | 视频时长，如 `"5s"` |
| `resolution` | string | 分辨率，如 `"1080p"` |
| `n` | integer | 生成数量 |
| `transno` | string | 交易流水号 |

### 请求示例

```json
{
    "model": "keling-2.1",
    "llmcatelogid": "文生视频",
    "prompt": "A beautiful sunset over the ocean",
    "duration": "5s",
    "resolution": "1080p"
}
```

### 响应格式

视频生成通常为异步任务，提交后返回任务信息：

```json
{
    "id": "luid_xxx",
    "object": "video.generation",
    "model": "keling-2.1",
    "status": "submitted",
    "taskid": "task_xxx",
    "created": 1716912000
}
```

通过 `/v1/tasks?taskid=xxx` 查询任务状态。

---

## POST /v1/image/generations

图像生成接口。

### 必填参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `model` | string | 模型名称，如 `"jimeng-4.0"` |
| `llmcatelogid` | string | 目录类型，如 `"文生图"` / `"图生图"` |
| `prompt` | string | 生成提示词 |

### 可选参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `image_url` | string | 图生图时提供参考图 URL |
| `size` | string | 尺寸，如 `"1024x1024"` |
| `n` | integer | 生成数量 |
| `style` | string | 风格参数 |
| `quality` | string | 质量参数 |
| `transno` | string | 交易流水号 |

### 请求示例

```json
{
    "model": "jimeng-4.0",
    "llmcatelogid": "文生图",
    "prompt": "A beautiful sunset over the ocean",
    "size": "1024x1024",
    "n": 1
}
```

### 响应格式

响应格式取决于上游模型配置（同步返回图像数据，异步返回任务信息）：

```json
{
    "id": "luid_xxx",
    "object": "image.generation",
    "model": "jimeng-4.0",
    "status": "submitted",
    "taskid": "task_xxx",
    "created": 1716912000
}
```

---

## GET /v1/tasks

查询异步任务状态。

### 必填参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `taskid` | string | 任务 ID |

### 请求示例

```
GET /llmage/v1/tasks?taskid=task_xxx
```

### 响应格式

```json
{
    "status": "ok",
    "data": {
        "status": "SUCCEEDED",
        "output": [...]
    }
}
```

任务状态值: `UNKNOWN` / `SUCCEEDED` / `FAILED`

---

## GET /v1/models

列出可用模型列表。

### 可选参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `lctype` | string | 按目录类型过滤 |
| `orderby` | string | 排序字段 |

### 请求示例

```
GET /llmage/v1/models
```

### 响应格式

```json
{
    "object": "list",
    "data": [
        {
            "id": "qwen3-max",
            "object": "model",
            "created": 1748044800,
            "owned_by": "opencomputing.ai"
        }
    ]
}
```

---

## 通用说明

### 认证

所有接口需要 Bearer Token 认证，请求头中携带:

```
Authorization: Bearer <your_api_key>
```

### 余额检查

每次请求都会自动调用 `checkCustomerBalance()` 进行余额检查：
- 如果模型属于用户所在组织（`llm.ownerid == userorgid`），则跳过余额检查
- 否则检查 tpac 余额或本地余额
- 余额不足时返回 429 状态码

### 计费

请求成功后自动创建 `llmusage` 记录，状态为 `created`。后台定时任务会定期执行计费流程。
