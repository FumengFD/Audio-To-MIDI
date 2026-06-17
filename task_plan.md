# 任务计划

## Phase 1: 集成 midi2mscz.py
- 复制脚本到 `src/score/`
- 安装缺失依赖 `mido`
- 修改脚本去掉 argparse main，暴露 `pipeline_midi(midi_path)` 函数供调用

## Phase 2: 添加"导出 MSCZ"按钮
- 工具栏加按钮
- 扒谱完成后可用
- 点击 → 量化 MIDI → MuseScore 生成 MSCZ → 修复乐器 → 排版美化
- 输出 `歌名_final.mscz`

## Phase 3: 推送
