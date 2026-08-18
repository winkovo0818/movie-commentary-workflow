# ChatCut 适配合同

## 边界

`visual_edit.json` 和 `audio_mix_plan.json` 是创意事实源。`chatcut-timeline-manifest.json` 是可重复生成的执行清单，`production/chatcut-sync.json` 是外部 ChatCut 现场的执行账本。不得把 ChatCut 运行时 ID 写回导演方案。

## 时间换算

- 导演方案使用整数毫秒；ChatCut 时间线使用整数帧。
- 编译器对共享边界使用同一个 half-up 换算，保证相邻画面块在帧级连续。
- `durationInFrames = endFrame - fromFrame`。
- `playbackRate = 原片区间时长 / 实际时间线帧时长`，使源入点和源出点都得到保留。
- 任一画面块换算后少于一帧都属于不可执行错误。

## 逻辑轨道

| 逻辑键 | ChatCut 类型 | 用途 |
|---|---|---|
| `picture` | video | 主画面，通常复用新时间线的 V1 |
| `narration` | audio / anchor | 锁定旁白和字幕来源 |
| `source-audio` | audio / anchor | 独立导入的原片对白或环境声 |
| `music` | audio / follower | 配乐，自动跟随旁白 duck |

画面素材中的嵌入音频默认静音。只有 `visual_edit.clips[].source_audio=true` 时保留该画面块的原声。

## 素材映射

素材映射文件结构：

```json
{
  "schema_version": 1,
  "project_id": "真实 ChatCut 项目 ID",
  "timeline_id": "真实 ChatCut 时间线 ID",
  "assets": {
    "原片路径或 source key": "真实 assetId",
    "旁白路径或 source key": "真实 assetId"
  }
}
```

可以省略尚未取得的 ID，但素材、项目或时间线 ID 任一缺失时 manifest 会保持 `ready=false`，不得执行条目批次。

## 声音事件

- `narration`：默认从 `visual_edit.narration` 取得素材；未写 `source_start_ms` 时，默认源时间与时间线时间一致。
- `music`：必须有 `source`；未写 `source_start_ms` 时从音乐素材起点播放。
- `source_dialogue` / `ambience`：有独立 `source` 时放入 `source-audio` 轨；没有独立源时列入 `manual_audio_events`，由总导演确认是否通过画面嵌入音频执行。
- `silence`：不创建条目，只保留为审计事件。
- 同一逻辑音轨上的事件不得重叠。确实需要并行或交叉声音时，在事件中使用不同的 `track_key`；编译器会为自定义键建立独立音轨。

## 同步状态

`production/chatcut-sync.json` 必须符合 `schemas/chatcut-sync.schema.json`，并维护：

- 当前 ChatCut 项目和时间线；
- manifest 与导演方案指纹；
- 逻辑轨道、素材和导演 clip/event 到 ChatCut 条目的映射；
- 已提交批次；
- 最近结构和视觉验证；
- 用户手工改动状态。

同步状态只描述执行事实，不能宣布用户创意认可。

## 执行限制

- 不直接操作 ChatCut 数据库。
- 不通过本地 FFmpeg 生成扁平化主交付物。
- 不猜测或复用另一个项目的 ID。
- 不把字幕当普通条目。
- 不在未读取现场的情况下覆盖已有时间线。
- 不把工具调用成功当作视觉验证。
