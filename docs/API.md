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
| `catelogid` | string | 目录类型ID，默认 `"t2t"`，也支持中文名（向后兼容） |
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
| `catelogid` | string | 目录类型ID，如 `"t2v"` / `"i2v"` / `"r2v"` |
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
    "catelogid": "t2v",
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
| `catelogid` | string | 目录类型ID，如 `"t2i"` |
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
    "catelogid": "t2i",
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
| `catelogid` | string | 按目录类型过滤 |
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

### catelogid 目录类型ID对照表

| ID | 中文名 | 说明 |
|----|--------|------|
| `t2t` | 文生文 | 文本生成（默认） |
| `t2i` | 文生图 | 图像生成 |
| `t2v` | 文生视频 | 文本生成视频 |
| `i2v` | 图生视频 | 图像生成视频 |
| `r2v` | 参考生视频 | 参考图像生成视频 |
| `tts` | 语音合成 | 文本转语音 |
| `asr` | 语音识别 | 语音转文本 |
| `vision` | 图理解 | 图像理解 |
| `ai_search` | AI搜索 | AI搜索 |
| `digital_human` | 数字人 | 数字人 |
| `music_gen` | 音乐生成 | 音乐生成 |
| `text_cls` | 文本分类 | 文本分类 |
| `3d_gen` | 3D生成 | 3D模型生成 |
| `video_tool` | 视频工具 | 视频处理工具 |
| `translate` | 翻译 | 文本翻译 |

> 向后兼容：catelogid 参数同时支持新ID（如 `"t2v"`）和旧中文名（如 `"文生视频"`），推荐使用新ID。

### 参数统一

所有 v1 接口统一使用 `catelogid` 参数标识目录类型，替代原有的 `lctype` / `llmcatelogid`。

### 认证

所有接口需要 Bearer Token 认证，请求头中携带:

```
Authorization: Bearer ***
```

### 余额检查

每次请求都会自动调用 `checkCustomerBalance()` 进行余额检查：
- 如果模型属于用户所在组织（`llm.ownerid == userorgid`），则跳过余额检查
- 否则检查 tpac 余额或本地余额
- 余额不足时返回 429 状态码

### 计费

请求成功后自动创建 `llmusage` 记录，状态为 `created`。后台定时任务会定期执行计费流程。
