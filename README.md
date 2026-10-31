# 阿蕾奇诺 Q 版 · Codex / ChatGPT 桌面版虚拟宠物

给 Codex / ChatGPT 桌面版用的自定义宠物皮肤。装好之后，她会站在窗口角落，会呼吸、会跟着你的操作切换状态、鼠标移动时会转视线。

<p align="center">
  <img src="preview/demo-v1.gif" width="216" alt="preview">
</p>

仓库里有两套皮肤，造型不同，按喜好选一个（也可以两个都装）：

| 皮肤 | 造型 | 目录 |
|---|---|---|
| **持镰版**（推荐） | 白发、赤红 X 瞳、黑红礼服，右手持迷你镰刀 | `pets/arlecchino-chibi/` |
| **原型版** | 黑发礼帽、黑红礼服，由单张立绘确定性派生 | `pets/arlecchino-chibi-v2/` |

## 快速安装

宠物就是一个文件夹，放进 `~/.codex/pets/` 下即可。

### Windows（PowerShell）

```powershell
git clone https://github.com/<你的用户名>/arlecchino-codex-pet.git
cd arlecchino-codex-pet
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

装指定一个：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Pet arlecchino-chibi
```

### macOS / Linux

```bash
git clone https://github.com/<你的用户名>/arlecchino-codex-pet.git
cd arlecchino-codex-pet
bash install.sh              # 全部安装
bash install.sh arlecchino-chibi   # 只装一个
```

### 手动安装

把 `pets/<皮肤名>/` 整个目录复制到：

| 系统 | 目标路径 |
|---|---|
| Windows | `C:\Users\<你>\.codex\pets\` |
| macOS / Linux | `~/.codex/pets/` |

复制完目录结构应该是：

```
~/.codex/pets/arlecchino-chibi/
├── pet.json
└── spritesheet.webp
```

> **必须彻底退出应用再重新打开**（托盘图标右键退出，不是最小化）。应用只在启动时扫描宠物目录。
>
> 然后在 设置 → 个性化 → Pets（或 Work 模式标题旁那只宠物图标）里选择「阿蕾奇诺」。

## 卸载

删掉对应目录，重启应用即可：

```bash
rm -rf ~/.codex/pets/arlecchino-chibi
```

Windows：

```powershell
Remove-Item -Recurse "$HOME\.codex\pets\arlecchino-chibi"
```

## 图集规格

两套皮肤都符合 Codex 的 v2 宠物契约：

| 项目 | 值 |
|---|---|
| 尺寸 | 1536 × 2288 |
| 网格 | 8 列 × 11 行 |
| 单元格 | 192 × 208，透明背景 |
| 元数据 | `pet.json` 中 `spriteVersionNumber: 2` |

各行含义：

| 行 | 状态 | 帧数 |
|---|---|---|
| 0 | idle（第 7 格为正面中性帧，用于视线归零） | 6 + 1 |
| 1 / 2 | 向右跑 / 向左跑 | 8 / 8 |
| 3 | 挥手 | 4 |
| 4 | 跳跃 | 5 |
| 5 | 失败 / 萎靡 | 8 |
| 6 | 等待 | 6 |
| 7 | 工作 | 6 |
| 8 | 完成展示 | 6 |
| 9 / 10 | 16 个顺时针朝向（每行 8 格，000° → 337.5°） | 8 / 8 |

## 两套皮肤的差别

**持镰版**：11 行动作是逐行生成的，每个状态有独立姿态，朝向行有真实的转头。

**原型版**：全部 88 格由同一张正面立绘做仿射变换（缩放、绕脚底旋转、镜像）派生，没有任何重绘。好处是形象百分之百一致、体积极小；代价是挥手、失败这类需要肢体变化的状态只有整体形变，朝向行是「宽度压缩 + 侧倾」伪装的转身，不是真 3D 转头。

<p align="center">
  <img src="preview/demo-v2.gif" width="216" alt="preview v2">
</p>

## 自己做一个

`tools/` 下有两个可以直接复用的脚本（需要 Python 3 与 Pillow、numpy）：

- `build_atlas.py`：把「一行多姿势」的图切分、抠色、归一化基线，拼成 8×11 图集
- `build_from_frame.py`：只用一张立绘，靠仿射变换派生 88 格，零重绘

```bash
python tools/build_from_frame.py --src path/to/your_character.png --out build/
```

产物 `build/spritesheet.webp` + 一个 `pet.json` 就是完整宠物包。

拼装时有两个容易踩的坑，脚本里已经处理好：

1. 每行帧数是硬要求，多出来的列必须留全透明，否则校验报 `unused column is not transparent`
2. WebP 必须用 `exact=True` 保存，否则全透明像素会被写回 RGB，触发 `transparent RGB residue` 报错

## 许可与声明

- 本仓库的脚本与打包代码：MIT，见 [LICENSE](LICENSE)
- 角色「阿蕾奇诺」及《原神》相关设定的著作权归米哈游（HoYoverse）所有。本仓库的美术素材是**非商业同人作品**，仅供个人使用，不得用于商业用途。详见 [NOTICE.md](NOTICE.md)
- 与米哈游、OpenAI 均无关联，未获官方授权或背书

## English

Custom pet skins for the Codex / ChatGPT desktop app. Copy a folder from `pets/` into `~/.codex/pets/`, fully quit and relaunch the app, then pick the pet under Settings → Personalization → Pets.

`arlecchino-chibi` has per-state generated poses; `arlecchino-chibi-v2` is derived from a single front-view illustration using affine transforms only. Both follow the v2 contract: 1536×2288, 8×11 grid, 192×208 cells, `spriteVersionNumber: 2`.

Fan art. Arlecchino and Genshin Impact are © HoYoverse. Non-commercial personal use only. Not affiliated with HoYoverse or OpenAI.
