---
name: movie-chatcut-timeline
description: 将锁定的电影解说 visual_edit.json 与 audio_mix_plan.json 编译、导入并同步为可继续手工编辑的 ChatCut 项目时间线。需要把电影原片、旁白、音乐、字幕和镜头计划送入 ChatCut，制作或更新竖屏/横屏样片，恢复中断的 ChatCut 组装，核对 ChatCut 时间线是否忠实执行导演方案，或在用户手工改动后判断如何续做时使用。
---

# 电影解说 ChatCut 时间线

把 ChatCut 作为可编辑执行层。保留原始素材、独立轨道、裁切、源时间码、旁白和字幕；不得先在本地压成一个不可编辑的视频再导入。

## 读取现场

1. 读取 `AGENTS.md`、影片 `project.json`、`production/state.json`、锁定的导演方案和声音方案。
2. 读取 [references/chatcut-contract.md](references/chatcut-contract.md)。
3. 加载 ChatCut 的 `chatcut-plugin-basics`、`asset-import` 和 `verification` 技能；需要配音、字幕或导出时再加载对应技能。
4. 如果 `workflow_control.status` 为 `PAUSED`，且用户没有明确恢复，立即停止。
5. 要求样片方案处于 `DIRECTOR_PROXY_PLAN_LOCKED`，或正式方案处于 `DIRECTOR_PLAN_LOCKED`。不得把未锁定候选写入正式 ChatCut 时间线。
6. 读取现有 `production/chatcut-sync.json`。文件不存在表示尚未同步，不表示 ChatCut 项目不存在。

## 编译导演方案

从仓库根目录运行：

```bash
python .codex/skills/movie-chatcut-timeline/scripts/compile_chatcut_timeline.py \
  --visual-edit "/absolute/path/visual_edit.json" \
  --audio-mix-plan "/absolute/path/audio_mix_plan.json" \
  --asset-map "/absolute/path/chatcut-asset-map.json" \
  --output "/absolute/path/chatcut-timeline-manifest.json" \
  --timeline-name "电影解说｜样片" \
  --fps 30 --width 1080 --height 1920
```

第一次导入前可以省略 `--asset-map`。编译器仍会生成素材需求清单；完成 ChatCut 导入并取得真实 `assetId` 后，补齐映射并重新编译。禁止猜测项目、时间线、轨道、素材或条目 ID。

## 建立或恢复 ChatCut 现场

1. 使用 ChatCut 官方工具创建或定位用户指定项目，并立即提供可打开的编辑器界面。
2. 新建独立时间线；样片、完整版本和重大改版使用不同时间线，不覆盖用户正在评审的版本。
3. 通过 ChatCut 导入流程导入清单中的原片、旁白、音乐和独立声音。每批最多四个本地文件；保存返回的真实素材 ID。
4. 建立画面、旁白和音乐轨道。旁白轨设为 `anchor`，音乐轨设为 `follower`；用户没有要求时不要自定 duck 深度。
5. 把真实项目、时间线、轨道和素材 ID 写入 `production/chatcut-sync.json`，再重新编译清单。
6. 如果同步文件与 ChatCut 现场不一致，先读取当前项目和时间线；不得直接清空或重建用户时间线。

## 执行清单

1. 按 manifest 的 `track_specs` 建立或复用轨道，并把逻辑轨道键解析为稳定轨道 ID。
2. 逐批把 `item_batches` 中的 `asset_ref` 和 `track_ref` 替换为同步文件中的真实 ID。
3. 每批先调用 ChatCut 条目编辑的校验模式；通过后原样提交。失败时停止当前批次，记录错误，不继续后续批次。
4. 画面条目必须保留 `fromFrame`、`durationInFrames`、`sourceStartFromInSeconds` 和 `playbackRate`。不得为了消除校验错误自行换镜头。
5. 旁白和音乐保持独立音频条目。只有导演方案明确要求时才保留原片声音。
6. 为旁白启用字幕，并把字幕来源明确绑定到旁白轨。字幕不是普通时间线条目，不通过条目编辑创建。
7. 每个成功批次写入条目 ID 与 manifest 指纹，使中断后只继续未完成批次。

## 处理用户手工编辑

- ChatCut 时间线是用户可修改的事实现场。同步前重新读取相关轨道和条目。
- 现场仍符合锁定方案时更新同步记录，不重复创建条目。
- 检测到用户移动、裁切、替换或删除受管条目时，将同步状态设为 `USER_MODIFIED`，保存差异并交给总导演判断。
- 未经用户明确要求，不覆盖用户改动。采用用户改动时生成新版导演方案并重新锁定；拒绝改动时才按锁定方案恢复。

## 验证与交付

1. 结构验证：画面主轨无空档和重叠，条目数量、顺序、源区间、时长、轨道和声音状态符合 manifest。
2. 视觉验证：检查开头、结尾、所有关键事实锚点和每个批次至少一个组合画面；必须实际查看像素。
3. 声音验证：旁白覆盖、原片声音接管、音乐轨和字幕来源符合声音方案。
4. 验证通过后把同步状态设为 `VERIFIED`，记录 ChatCut 项目、时间线、manifest 与导演方案指纹。
5. 样片交付为可播放、可编辑的 ChatCut 时间线。只有用户要求导出时才触发导出。

ChatCut 技术通过不等于用户创意认可。用户认可样片后，仍由总导演推进 `USER_SAMPLE_APPROVED` 和后续正式锁。
