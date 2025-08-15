# 《马力欧卡丁车DS》汉化

[![CC-BY-NC-SA 4.0](https://mirrors.creativecommons.org/presskit/buttons/88x31/svg/by-nc-sa.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode)

## 基本说明

本项目是对 Nintendo DS 游戏《马力欧卡丁车DS》（<span lang="ja">マリオカートDS</span>）的简体中文本地化。

译名以最新的任天堂官方中文翻译为准，部分简繁不一致的译名参考任天堂译名习惯选取繁体中文译名。

关于 DS Download Play：由于 DS Download Play 受字库大小限制较严重，因此本项目提供两种补丁，即“通常版”和“Download Play 版”。前者无法正常使用 DS Download Play 功能；后者虽然能够正常使用 DS Download Play 功能，但字体表现受到限制（例如不能使用日文假名）。请按照需求使用。并且由于 DS Download Play 存在签名校验，少量文本无法翻译成中文，但基本不影响正常游戏。

本汉化以补丁形式提供，如需转载，请保留此说明。

## 汉化名单

**Monado 汉化组 汉化**

- **破解**：[Xzonn](https://space.bilibili.com/16114399)、[洗涤子](https://space.bilibili.com/4977282)
- **翻译**：[无敌阿尔宙斯](https://space.bilibili.com/22012231/)
- **美工**：[扭TYPE-小光](https://space.bilibili.com/25027421)
- **测试**：[库帕二世](https://space.bilibili.com/401201102)

## 汉化感言

**Xzonn**：虽然这游戏文本量不大，不用汉化也基本能玩，但是有个接近官中的版本总是好的。我最近要开始忙起来了，一些汉化项目不一定能投入太多时间精力，希望大家能够理解。

**扭TYPE-小光**：上大学时，正值 NDS 与 PSP 旷日持久的掌机大战，也与好友们为 NDS 和 PSP 各执一词。在多年，能够有幸参与到《马力欧卡丁车DS》的汉化，就像是与老友的久别重逢。希望通过汉化，能和大家一起回到那个传统掌机的黄金时代，重新感受掌上游戏的乐趣与美好。

## 使用方式

请下载压缩包并解压，按照补丁应用工具“NitroPatcher”的说明进行操作。补丁压缩包中包含了 Microsoft Windows 平台的补丁应用工具，其他平台的工具可通过下方下载地址获取。

软件使用视频教程：<https://www.bilibili.com/video/BV1oH1xYXEdb/?t=69>

原始 ROM 为日本版，校验码（[No-Intro 0228](https://datomatic.no-intro.org/index.php?page=show_record&s=28&n=0228)）：

- CRC32：`226e8db6`
- MD5：`67b9666b1dbaaf1e8ca03bf7786ed5b6`
- SHA-1：`a4c790b6cd1e45a9728001081845c17f06985a17`

补丁压缩包下载地址：

- GitHub：<https://github.com/Qi-Busiyi-Hanhuazu/MKDSChsLocalization/releases/download/v1.0.0/MKDSChsLocalization.v1.0.0.zip>
- 百度网盘：<https://pan.baidu.com/s/1KLHwLwhdHQzB2qojiKH21A?pwd=mkds>

补丁应用工具下载地址（Windows/Linux/macOS/Android）：

- GitHub：<https://github.com/Xzonn/NitroPatcher/releases/latest/>
- 百度网盘：<https://pan.baidu.com/s/1vXynSX1WauU3FeGHDnrDfg?pwd=ntro>

## 截图预览
![截图](assets/images/screenshot-01.png) ![截图](assets/images/screenshot-02.png) ![截图](assets/images/screenshot-03.png)

## 授权协议

本项目使用 **[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode)** 协议授权。若您想基于本项目进行二次创作，请遵守协议内容。这些内容主要包括：

- **署名**：您必须标明本项目的作者，并在您的作品中提供指向本项目的链接。
- **非商业性使用**：您不得将本项目用于商业目的。
- **相同方式共享**：若您基于本项目进行二次创作，您必须以相同的协议授权您的作品。

请阅读本项目的 **[完整授权协议](LICENSE.txt)** 以了解更多信息。

## 构建方式
### 前提条件

- [Python 3.10+](https://www.python.org/downloads/)（`pip install -r requirements.txt`）
- [PowerShell 5.0+](https://learn.microsoft.com/powershell/)
- 字体文件（默认读取以下文件：`files/fonts/Zfull-GB.ttf`）

### 构建
在 PowerShell 中运行：

```
. scripts\build_patch.ps1
```
