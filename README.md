# 🎵 Audio-To-MIDI

音频文件转mid文件 — 多乐器音源分离 + 分轨转录 → MIDI。
MIDI可导入[MuseScore](https://musescore.com/)显示谱面。

## 使用模型
| 模型 | 用途 |
|------|------|
| [Demucs](https://github.com/facebookresearch/demucs) | 音源分离 |
| [ADTOF-pytorch](https://github.com/xavriley/ADTOF-pytorch) | 鼓组转录 |
| [Basic Pitch](https://github.com/spotify/basic-pitch) | 旋律转录 |
| [Transkun](https://github.com/Natooz/Transkun) | 钢琴转录 |

## 管线

```
FLAC/MP3/WAV → Demucs 分轨 → 分轨转录 → MIDI 合并 + 量化 → MIDI
                                  │
                    ┌─────────┬───┴───┬──────────┐
                   鼓        贝斯/人声  吉他       钢琴
                 ADTOF      Basic Pitch Basic Pitch Transkun
                (88.5%)                          (98.3%)
```

## 功能

- 🎛️ 6 声部音源分离（鼓/贝斯/人声/吉他/钢琴/其他）
- 🥁 鼓组专用转录 (ADTOF, 88.5% F1)
- 🎹 钢琴专用转录 (Transkun, 98.3% F1)
- 🎸 贝斯/人声/吉他 (Basic Pitch)
- 📐 MIDI 节拍量化 + 手动 BPM
- 💾 导出 MIDI

## 依赖

| 库 | 用途 | 安装 |
|---|---|---|
| PyTorch 2.7+ | 深度学习框架 | 见下方 |
| torchaudio | 音频加载 | 随 PyTorch 安装 |
| demucs | 音源分离 | `pip install demucs>=4.0` |
| adtof-pytorch | 鼓组转录 | `pip install git+https://github.com/xavriley/ADTOF-pytorch.git` |
| basic-pitch | 旋律转录（贝斯/人声/吉他） | `pip install basic-pitch>=0.3` |
| transkun | 钢琴转录 (98.3% F1) | `pip install transkun>=2.0` |
| transformers | ADTOF 依赖（**必须 4.48.3**） | `pip install transformers==4.48.3` |
| pretty-midi | MIDI 读写 | `pip install pretty-midi>=0.2` |
| librosa / soundfile | 音频处理 | `pip install librosa>=0.10 soundfile>=0.12` |
| PySide6 / pyqtgraph | 图形界面 | `pip install PySide6>=6.7 pyqtgraph>=0.13` |
| matplotlib / numpy | 数值计算 | `pip install matplotlib>=3.8 numpy>=1.26` |

## 安装

### 1. 安装 PyTorch

```bash
# CUDA 12.8（推荐，有 NVIDIA 显卡）
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128

# CPU 版
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### 2. 安装项目依赖

```bash
cd music-transcriber
pip install -e .
```

### 3. 修复 transformers 版本（必须）

```bash
pip install transformers==4.48.3
```

> ⚠️ 新版 transformers 会导致 ADTOF 模型报错 `tuple index out of range`

## 模型

所有模型权重**无需手动下载**：

- Demucs：首次扒谱时自动从 torch hub 下载（~80MB，需联网一次）
- ADTOF / Basic Pitch / Transkun：已随 pip 包安装

## 启动

```bash
python -m src.main
```

或双击 `Audio-To-MIDI.exe`

## 支持的格式

- 输入：FLAC, WAV, MP3, OGG, M4A, AIFF
- 输出：MIDI

## 项目结构

```
src/
├── gui/              PySide6 图形界面
├── separation/       音源分离 (Demucs)
├── transcription/    音符转录 (ADTOF + Transkun + Basic Pitch)
├── midi/             MIDI 合并 + 量化
├── pipeline.py       总管线
└── main.py           入口
```
