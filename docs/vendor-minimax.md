# MiniMax 供应商接入记录

## 供应商信息

| 项目 | 值 |
|------|-----|
| 供应商名称 | MiniMax (上海稀宇科技有限公司) |
| 平台网址 | https://platform.minimaxi.com |
| API文档 | https://platform.minimaxi.com/docs/api-reference/text-chat-openai |
| 定价页面 | https://platform.minimaxi.com/subscribe/token-plan?tab=api-enterprise |
| API基础URL | https://api.minimaxi.com/v1 (upapp.baseurl) |
| 系统upappid | minimax |
| 系统providerid | ww4e_kfX3Lh65Sdys0Vku |
| API认证方式 | Bearer Token (Authorization: Bearer *** |

## 已接入模型 (共11个, 截至2026-06-12)

### 文本生成 (t2t) — 定价项目: 5jmzupARABxkDFwUraFiQ

| 模型名称 | model | llm.id | 状态 | httpapi |
|----------|-------|--------|------|---------|
| **MiniMax M3** | MiniMax-M3 | mm3_MiniMax_M3 | 新增 | minimax_openai t2t |
| MiniMax M2.7 | minimax-m2.7 | oiLvLl75qNX9IQkWFm60i | 已有 | t2t |
| **MiniMax M2.7 Highspeed** | MiniMax-M2.7-highspeed | mm_m27_highspeed | 新增 | minimax_openai t2t |

### 视频生成 (i2v) — 定价项目: 0V89eilc_UQ2KiZIRJO8M

| 模型名称 | model | llm.id | 状态 |
|----------|-------|--------|------|
| MiniMax Hailuo 2.3 | MiniMax-Hailuo-2.3 | AU1f40HV3tqFjxcVWWpyR | 已有, 补充ppid |
| 海螺参考生视频 | S2V-01 | oks-VG9D8p2b0Agvs-LeQ | 已有, 补充ppid |

### 语音合成 (tts) — 定价项目: mm_tts_pricing (新增)

| 模型名称 | model | llm.id | 状态 |
|----------|-------|--------|------|
| speech-2.6-hd | speech-2.6-hd | q6rdMUsGD1z3S3NyZh_A_ | 已有, 补充ppid |
| speech-2.6-turbo | speech-2.6-turbo | CEYD4YWRxjCj4k_6bpzIM | 已有, 补充ppid |
| speech-2.5-hd-preview | speech-2.5-hd-preview | Si2g0XJ9ym3P5jlrdmcfB | 已有, 补充ppid |

### 音乐生成 (music_gen) — 定价项目: fQzkUeS6t6NBz_Fu4Fi77

| 模型名称 | model | llm.id | 状态 |
|----------|-------|--------|------|
| Music 2.6 | music-2.6 | dleFKyYSSllCl70etn7yU | 已有 |
| Music 2.5 | music-2.5 | tTREa9nNy3yIRxywQLjvT | 已有 |
| Music 2.0 | music-2.0 | ns7egG9aXi91wjI62yKfu | 已有, 补充ppid |

## 定价信息

### 文本模型 (元/百万tokens) — 5jmzupARABxkDFwUraFiQ

| 模型 | 输入 | 输出 | 缓存 | 备注 |
|------|------|------|------|------|
| MiniMax-M3 | ¥2.1 | ¥8.4 | ¥0.42 | ≤512K永久五折 |
| MiniMax-M2.7 | ¥2.1 | ¥8.4 | - | 五折 |
| MiniMax-M2.7-highspeed | ¥4.2 | ¥16.8 | - | - |
| MiniMax-M2.5 | ¥2.1 | ¥8.4 | - | - |
| MiniMax-M2.5-highspeed | ¥4.2 | ¥16.8 | - | - |
| M2-her | ¥2.1 | ¥8.4 | - | - |

### TTS (元/万字符) — mm_tts_pricing

| 模型 | 单价 |
|------|------|
| speech-2.6-hd | ¥3.5 |
| speech-2.6-turbo | ¥2.0 |
| speech-2.5-hd-preview | ¥3.5 |

### 视频 (元/次) — 0V89eilc_UQ2KiZIRJO8M

| 模型 | 分辨率 | 时长 | 单价 |
|------|--------|------|------|
| Hailuo-2.3 | 768P | 6s | ¥2.00 |
| Hailuo-2.3 | 768P | 10s | ¥3.50 |
| Hailuo-2.3 | 1080P | 6s | ¥2.00 |
| Hailuo-2.3-Fast | 768P | 6s | ¥2.25 |

### 音乐 (元/次) — fQzkUeS6t6NBz_Fu4Fi77

| 模型 | 单价 |
|------|------|
| Music-2.6/2.5/2.0 | ¥1.0 |

## httpapi配置

### minimax_openai t2t (新增, id=mm3_openai_t2t)

M3/M2.7-highspeed使用的OpenAI Chat Completions兼容接口。
API地址由upapp.minimax.baseurl决定: https://api.minimaxi.com/v1/chat/completions

apiinfo:
```json
{
  "response_mode": "stream",
  "use_session": true,
  "method": "POST",
  "chunk_match": "data: ",
  "headers": [
    {"name": "Content-Type", "value": "application/json"},
    {"name": "Authorization", "value": "Bearer ${apikey}"}
  ],
  "data": [
    {"name": "model", "value": "${model}"},
    {"name": "messages", "value": "${messages}"},
    {"name": "stream", "value": true}
  ],
  "resp": [
    {"name": "content", "value": "choices[0].delta.content"},
    {"name": "usage", "value": "usage"}
  ]
}
```

## SQL文件

`scripts/minimax_m3_add.sql` — 包含11条SQL语句:
1. INSERT httpapi (minimax_openai t2t)
2. INSERT llm (MiniMax-M3)
3. INSERT llm (MiniMax-M2.7-highspeed)
4. INSERT llm_api_map (M3)
5. INSERT llm_api_map (M2.7-highspeed)
6. UPDATE llm_api_map ppid × 6 (视频/TTS/音乐)
7. INSERT pricing_program (mm_tts_pricing)
8. INSERT pricing_program_timing (TTS定价)
9. UPDATE 5jmzup timing (追加M3定价)
10. UPDATE 5jmzup spec (添加M3到模型选项)

## 变更记录

| 日期 | 操作 |
|------|------|
| 2026-06-12 | 新增M3+M2.7-highspeed, 补齐Hailuo/S2V/TTS/Music定价 |
