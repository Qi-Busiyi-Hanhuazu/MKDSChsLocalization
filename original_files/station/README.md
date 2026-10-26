# Station 原始资源

本目录保存二次转发所需的原始资源，来源为 Download Station Volume 1，原镜像 SHA-1：`f18b55f3e1259c03e10d0ecb549693b42905ceb5`。

- `ds_demo_client.srl`：原签名下载客户端，306,824 字节。

构建由 [`patch_dlp.py`](../../scripts/patch_dlp.py) 读取签名客户端，无需完整 Station ROM。Station 主机端由 [`dlpSource`](../../arm9_patch/dlpSource/) 自行编译。
