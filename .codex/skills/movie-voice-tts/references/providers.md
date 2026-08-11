# 配音供应商参考

## 选择基线

供应商、模型和接口可能变化，正式制作前必须用同一参考音频和同一短文案重新试听。下表只描述当前适配器的设计用途，不保证任意声音、语言或账户都得到相同结果：

| 供应商 | 当前方式 | 已观察到的最佳用途 | 已知问题 |
|---|---|---|---|
| 千问 | 注册长期音色后生成 | 原生中文电影旁白 | 跨语言时音色身份可能变化 |
| MiniMax | 上传音频、克隆长期音色后生成 | 补充对比和复用音色编号 | 跨语言口音需要单独试听 |
| Fish | 零样本参考音频或公共音色模型编号 | 同语言克隆、公开音色和原生时间戳 | 公共音色和跨语言效果取决于具体声音 |

不得假设只靠风格提示词就能修复跨语言发音或音色身份问题。

## 千问

- 密钥变量：`DASHSCOPE_API_KEY`
- 音色注册接口：`https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization`
- 语音生成接口：`https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer`
- 音色注册模型：`voice-enrollment`
- 目标模型：`qwen-audio-3.0-tts-plus`
- 本项目输出：WAV、24 kHz、单声道
- 当前系统音色和克隆音色的 `qwen-audio-3.0-tts-plus` 都不返回时间戳。需要字级时间轴时，使用火山引擎后备流程。
- 工作流程：
  1. 获取临时 OSS 上传凭证。
  2. 上传参考音频。
  3. 使用 `target_model` 创建长期音色。
  4. 轮询 `query_voice`，直到状态为 `OK`。
  5. 使用返回的 `voice_id` 生成语音。

## MiniMax

- 密钥变量：`MINIMAX_API_KEY`
- 基础地址：`https://api.minimaxi.com/v1`
- 模型：`speech-2.8-hd`
- 本项目输出：MP3、32 kHz、单声道、128 kbps
- 原生时间戳：启用字幕并选择词级粒度；已经返回原生时间戳时，不再追加语音识别。
- 工作流程：
  1. 以 `voice_clone` 用途上传参考音频。
  2. 通过 `/voice_clone` 创建长期音色。
  3. 通过 `/t2a_v2` 生成语音。
- `language_boost` 根据目标语言设置为 `Chinese` 或 `English`。
- 中性试音保持语速 `1`、音量 `1`、音调 `0`。

## Fish Audio

- 密钥变量：`FISH_API_KEY`
- 当前模型：`s2.1-pro-free`
- 对应付费模型：`s2.1-pro`
- 本项目输出：MP3、单声道
- 原生时间戳：使用 `/v1/tts/stream/with-timestamp` 和 `s2.1-pro` 或 `s2.1-pro-free`。中文输出已经验证会为识别出的每个汉字返回一个对齐片段。
- 工作流程：
  1. 零样本克隆时，每次请求都附带参考音频及其准确逐字稿。
  2. 用户从 Fish 音色页选定公开音色时，直接把链接中的 32 位模型编号作为 `reference_id`，不再下载或重新克隆。
  3. 需要正式时间轴时，使用 `/v1/tts/stream/with-timestamp`；音频片段按事件顺序拼接，每个内部块只采用最后一份累计对齐快照。
  4. 原生对齐 JSON 保存字词级时间戳，SRT 仅是便于预览的分组结果，编导优先读取原生 JSON。
- 身份相似度和发音自然度都重要时，参考语言应与目标语言一致。
- 只有用户要求时才添加简短风格指令；先生成不带指令的基准版本。

## 火山引擎语音识别后备流程

- 密钥变量：`VOLCENGINE_APPID` 和 `VOLCENGINE_TOKEN`
- 提交接口：`https://openspeech.bytedance.com/api/v1/vc/submit`
- 查询接口：`https://openspeech.bytedance.com/api/v1/vc/query`
- 只有供应商没有原生时间戳，或现有音频确实需要重新对齐时才使用。
- 中文旁白使用 `language=zh-CN` 和 `caption_type=speech`。
- 保留完整原始 JSON，因为 `utterances[].words[]` 包含汉字及其毫秒级 `start_time` 和 `end_time`。
- 运行 `scripts/volc_asr.py`；已验证合同和失败处理见 [volc-asr.md](volc-asr.md)。

## 公平对比

- 三家使用含义和时长接近的同一段文案。
- 不得只对其中一份试音做响度标准化。
- 单独保存未处理的原始参考音频。
- 同语言结果和跨语言结果分别比较。
- 先判断发音，再判断情绪和音色。
