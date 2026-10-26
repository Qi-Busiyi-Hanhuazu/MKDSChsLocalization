# 汇编代码

使用 devkitARM 和 GNU Make 编译，由 `scripts/build_patch.ps1` 调用，编译产物保存在 `out`。

可在仓库根目录运行 `make -C arm9_patch clean` 清理编译产物。

- `replSource`：父机 ARM9 挂接点，按目录地址编译并写入。
- `downloadSource`：父子机共用的 overlay 范围及下载内存修正。
- `dlpSource`：Station 主机端及马车挂接代码。
- `childSource/2332C40`：马车子机启动前的 GGID 修正。
- `hosts/mkds.h`：马车原 SDK 函数定义和地址宏，Station 主机端直接调用 `FS_InitFile` 等原函数。
- `wifiSource`：Wi-Fi 赛道解锁，按地址原位修改赛道数量及列表指针。

Station 主机端编译到 `0x021CACE0`，与马车挂接代码作为共用段接入父机的 overlay 0、1，由游戏按原场景流程装载。原有代码和 BSS 地址保持不变，新增代码放在两者的 BSS 之后，占用范围计入 overlay 大小。`ds_demo` 的三个实际文件通过 XZP `formatVersion: 2` 加入 NitroFS。

overlay 的原 SDK 校验保持启用，构建时同步更新父机和子机 ARM9 中的表摘要及已修改镜像的摘要。overlay 2 下载区大小的调整也计入表摘要。

修改后的资源和系统文件放在 `temp/out`，由 `scripts/create_xdelta.py` 统一生成差分。Wi-Fi 修改结果放在 `temp/wifi_tracks`，以完整版为基准生成差分到 `out/wifi_tracks`。

`DlpFile` 文件表包含菜单和游戏程序。端口 12 的信息由宿主通过 `DlpInfo` 传入，Station 主机端原样复制，按表内的八字节文件名匹配文件。父机等待所有参与子机接收完毕后交回原游戏流程。

子机交接代码装载 ARM9，保存 60 字节 MB 上下文并恢复原游戏 GGID，随后调用签名客户端原启动助手，交回原程序。装载参数及原游戏 GGID 由构建脚本传入编译。

首次下载发送原签名 Station 客户端，第二次下载由 Station 主机端发送封装后的 clone boot 客户端，再由游戏原文件服务读取完整汉化资源。子机启动提示和所需汉字原位替换，保持原字体和压缩资源槽大小。

Wi-Fi 追加补丁由 `scripts/wifi_tracks.ps1` 单独打包，必须在完整汉化补丁之后应用。

二次下载格式参考 [dspatch](https://github.com/Gericom/dspatch/blob/32856c4b68c8e45d90fe135d5555a4596fbd2955/dspatch/DownloadStationPatcher.cs)。
