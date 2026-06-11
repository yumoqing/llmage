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

### 各模型输入参数明细

> 以下为各平台/模型的具体输入参数。调用时通过 `model` + `catelogid` 自动路由到对应供应商。

---

#### Vidu 平台

##### T2V - 文生视频

| 参数名 | 类型 | 必填 | 默认值 | 说明 | 可选值 |
|--------|------|------|--------|------|--------|
| `model` | string | 是 | `viduq3-pro` | 模型名称 | `viduq3-turbo`, `viduq3-pro` |
| `prompt` | string | 是 | - | 提示词 | - |
| `off_peak` | string | 否 | `N` | 错峰执行 | `Y`, `N` |
| `duration` | integer | 否 | `10` | 视频长度（1-16秒） | 1-16 |
| `ratio` | string | 否 | `16:9` | 长宽比 | `16:9`, `9:16`, `4:3`, `3:4`, `1:1` |
| `resolution` | string | 否 | `1080p` | 分辨率 | `540p`, `720p`, `1080p` |

##### I2V - 图生视频

| 参数名 | 类型 | 必填 | 默认值 | 说明 | 可选值 |
|--------|------|------|--------|------|--------|
| `model` | string | 是 | `viduq3-pro` | 模型名称 | `viduq3-pro`, `viduq3-turbo` |
| `prompt` | string | 是 | - | 提示词 | - |
| `image_file` | image | 是 | - | 首帧图片 | - |
| `off_peak` | string | 否 | `N` | 错峰执行 | `Y`, `N` |
| `duration` | integer | 否 | `10` | 视频长度（1-16秒） | 1-16 |
| `ratio` | string | 否 | `16:9` | 长宽比 | `16:9`, `9:16`, `4:3`, `3:4`, `1:1` |
| `resolution` | string | 否 | `1080p` | 分辨率 | `540p`, `720p`, `1080p` |

##### 2I2V - 首尾帧生视频

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `model` | string | 否 | `viduq2` | 模型名称 |
| `payload` | string | 是 | `2i2v` | 固定值 |
| `off_peak` | boolean | 否 | `false` | 错峰模式 |
| `images` | array | 是 | - | 两张图片URL `[首帧, 尾帧]` |
| `duration` | integer | 否 | `10` | 视频时长 |
| `prompt` | string | 是 | - | 提示词 |
| `audio` | boolean | 否 | `true` | 音频直出 |
| `seed` | integer | 否 | `12345` | 随机种子 |
| `aspect_ratio` | string | 否 | `16:9` | 画面比例 |
| `resolution` | string | 否 | `1080p` | 分辨率 |

##### Ref2V - 参考生视频 v2（主体模式）

> 使用主体（图片/视频/文字）生成视频，支持 viduq3-turbo/q3/q2-pro/q2/q1/2.0

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `model` | string | 是 | 模型名称 |
| `subjects` | array | 是 | 主体列表（最多7个图片/文字主体，每个主体最多3张图） |
| `prompt` | string | 是 | 提示词 |
| `audio` | boolean | 否 | 音视频直出 |
| `audio_type` | string | 否 | 音频类型 |
| `duration` | integer | 否 | 视频时长 |
| `seed` | integer | 否 | 随机种子 |
| `aspect_ratio` | string | 否 | 画面比例 |
| `resolution` | string | 否 | 分辨率 |
| `movement_amplitude` | string | 否 | 运动幅度 |
| `off_peak` | boolean | 否 | 错峰模式 |
| `auto_subjects` | boolean | 否 | 智能主体 |

##### Ref2V - 参考生视频 v2（非主体模式）

> 直接上传图片参考生成视频，支持 viduq3-mix/q3-turbo/q3/q2-pro/q2/q1/2.0

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `model` | string | 是 | 模型名称 |
| `images` | array | 是 | 参考图片URL列表（1-7张） |
| `videos` | array | 否 | 参考视频URL列表（仅viduq2-pro） |
| `prompt` | string | 是 | 提示词 |
| `audio` | boolean | 否 | 音视频直出 |
| `bgm` | boolean | 否 | 背景音乐 |
| `duration` | integer | 否 | 视频时长 |
| `seed` | integer | 否 | 随机种子 |
| `aspect_ratio` | string | 否 | 画面比例 |
| `resolution` | string | 否 | 分辨率 |
| `off_peak` | boolean | 否 | 错峰模式 |

##### Ref2V - 参考生视频 v1

| 参数名 | 类型 | 必填 | 默认值 | 说明 | 可选值 |
|--------|------|------|--------|------|--------|
| `model` | string | 是 | `viduq2-pro` | 模型名称 | `viduq2`, `viduq1`, `vidu2.0` |
| `prompt` | string | 是 | - | 提示词 | - |
| `off_peak` | string | 否 | `N` | 错峰执行 | `Y`, `N` |
| `duration` | integer | 否 | `10` | 视频长度 | - |
| `ratio` | string | 否 | `16:9` | 长宽比 | `16:9`, `9:16`, `4:3`, `3:4`, `1:1` |
| `resolution` | string | 否 | `1080p` | 分辨率 | `540p`, `720p`, `1080p` |

---

#### Seedance 平台（火山方舟）

##### T2V - 文生视频

| 参数名 | 类型 | 必填 | 默认值 | 说明 | 可选值 |
|--------|------|------|--------|------|--------|
| `model` | string | 是 | `doubao-seedance-2-0-260128` | 模型名称 | `doubao-seedance-2-0-260128`, `doubao-seedance-2-0-fast-260128` |
| `prompt` | string | 是 | - | 提示词 | - |
| `resolution` | string | 否 | `720p` | 尺寸 | `480p`, `720p`, `1080p` |
| `duration` | integer | 否 | `8` | 视频长度 | - |
| `ratio` | string | 否 | `1:1` | 宽高比 | `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `21:9`, `9:21` |

##### TI2V - 文图生视频

| 参数名 | 类型 | 必填 | 默认值 | 说明 | 可选值 |
|--------|------|------|--------|------|--------|
| `model` | string | 是 | `doubao-seedance-2-0-260128` | 模型名称 | `doubao-seedance-2-0-260128`, `doubao-seedance-2-0-fast-260128` |
| `prompt` | string | 是 | - | 提示词 | - |
| `image1_file` | image | 是 | - | 首帧图片 | - |
| `image2_file` | image | 否 | - | 尾帧图片 | - |
| `resolution` | string | 否 | `720p` | 尺寸 | `480p`, `720p`, `1080p` |
| `duration` | integer | 否 | `8` | 视频长度 | - |
| `ratio` | string | 否 | `1:1` | 宽高比 | `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `21:9`, `9:21` |

##### Ref2V - 参考生视频

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `model` | string | 是 | - | 模型名称 |
| `prompt` | string | 是 | - | 提示词 |
| `image_file` | image | 否 | - | 参考图片（支持数组，多张参考图） |
| `video_file` | video | 否 | - | 参考视频（支持数组） |
| `audio_file` | audio | 否 | - | 参考音频（支持数组） |
| `duration` | integer | 否 | `12` | 视频长度 |
| `resolution` | string | 否 | `720p` | 尺寸 |
| `ratio` | string | 否 | - | 宽高比 |

---

#### 通义万象（DashScope）

##### T2V - 文生视频

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `model` | string | 是 | - | 模型名称（如 `wan2.6-t2v`） |
| `prompt` | string | 是 | - | 提示词 |
| `negative_prompt` | string | 否 | - | 反向提示词 |
| `audio_file` | audio | 否 | - | 配音文件 |
| `size` | string | 否 | `1920*1080` | 视频尺寸 |
| `duration` | string | 否 | `15` | 视频时长 |

**size 可选值：** `832*480`, `480*832`, `624*624`, `1280*720`, `720*1280`, `960*960`, `1088*832`, `832*1088`, `1920*1080`, `1080*1920`, `1440*1440`, `1632*1248`, `1248*1632`

**duration 可选值：** `5`, `10`, `15`

##### I2V - 图生视频

可用模型：`wan2.6-i2v`, `wan2.6-i2v-flash`

> 输入参数与 T2V 类似，额外需要首帧图片。

##### 2I2V - 首尾帧生视频

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `model` | string | 是 | - | 模型名称 |
| `prompt` | string | 是 | - | 提示词 |
| `negative_prompt` | string | 否 | - | 反向提示词 |
| `image1_file` | image | 是 | - | 首帧图片 |
| `image2_file` | image | 是 | - | 尾帧图片 |
| `resolution` | string | 否 | `1080P` | 分辨率 |
| `duration` | integer | - | `5` | 固定5秒 |

##### Ref2V - 角色参考生视频

> 参考输入视频中的角色形象和音色，搭配提示词生成保持角色一致性的视频。可以输入1-3个人物视频，每个视频一个角色。

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `model` | string | 是 | - | 模型名称（如 `wan2.6-r2v`） |
| `prompt` | string | 是 | - | 提示词 |
| `video1_file` | video | 是 | - | 角色一视频 |
| `video2_file` | video | 否 | - | 角色二视频 |
| `video3_file` | video | 否 | - | 角色三视频 |
| `size` | string | 否 | `1920*1080` | 视频尺寸 |
| `duration` | string | 否 | `10` | 视频时长 |

**size 可选值：** 同 T2V

**duration 可选值：** `10`, `15`

##### IA2V - 图像音频生视频

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `image_file` | image | 是 | 图像 |
| `audio_file` | audio | 是 | 音频 |

---

#### 可灵（Kling）

##### T2V - 文生视频

| 参数名 | 类型 | 必填 | 默认值 | 说明 | 可选值 |
|--------|------|------|--------|------|--------|
| `model` | string | 是 | - | 模型名称 | `kling-v2-1-master`, `kling-v2-master`, `kling-v1-6`, `kling-v1` |
| `prompt` | string | 是 | - | 提示词 | - |
| `negative_prompt` | string | 否 | - | 反向提示词 | - |

---

#### 海螺（Hailuo/MiniMax）

##### TI2V - 图生视频

| 参数名 | 类型 | 必填 | 默认值 | 说明 | 可选值 |
|--------|------|------|--------|------|--------|
| `prompt` | string | 是 | - | 提示词 | - |
| `image_file` | image | 否 | - | 首帧图片 | - |
| `image_file1` | image | 否 | - | 尾帧图片 | - |
| `resolution` | string | 否 | `768P` | 尺寸 | `768P`, `1080P` |
| `duration` | integer | 否 | `6` | 视频长度 | `6`（6秒）, `10`（10秒） |

---

#### 快乐马（HappyHorse）

> 基于通义万象平台（tongyi-wan），输入参数与通义万象对应类型一致。

##### T2V - 文生视频

输入参数同通义万象 T2V。可用模型：`happyhorse-1.0-t2v`

##### I2V - 图生视频

输入参数同通义万象 I2V。可用模型：`happyhorse-1.0-i2v`

> **注意：** 图片参数名为 `image_file`（非 `image_url`），传入图片 URL。

##### Ref2V - 参考生视频

输入参数同通义万象 Ref2V，额外支持：

| 参数名 | 说明 |
|--------|------|
| `resolution` | 可选 `1080P`（默认）, `720P` |
| `ratio` | 可选 `16:9`（默认）, `9:16`, `3:4`, `4:3` |

可用模型：`happyhorse-1.0-r2v`（参考图像数量1-9张，支持多角色参考）

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

## GET /v1/pricing

获取模型定价展示信息。

### 必填参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `model` | string | 模型名称，如 `"qwen3.7-max"` |

### 可选参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `catelogid` | string | 目录类型ID，默认 `"t2t"` |

### 请求示例

```
GET /llmage/v1/pricing?model=qwen3.7-max
```

### 响应格式

```json
{
    "status": "ok",
    "data": {
        "ppid": "pp_xxx",
        "name": "qwen3.7-max",
        "pricing_type": "per_use",
        "display_text": "【通义千问 qwen3.7-max】定价:\n  - 输入Token: 12 元/百万 [模型=qwen3.7-max]\n  - 输出Token: 48 元/百万 [模型=qwen3.7-max]",
        "items": [...]
    }
}
```

### 错误响应

| 状态 | 说明 |
|------|------|
| error | 缺少 model 参数 |
| error | 模型不存在或无定价配置 |

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
