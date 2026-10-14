# 家庭成长记录网站

这是一个可在 Ubuntu/Docker 上自托管的家庭成长记录网站。访客可以浏览首页、兴趣角和成长日记；家长登录后可管理内容、配置音乐音源、备份家庭数据。

## 网页快照

![家庭成长记录网站首页快照](docs/readme-preview.png)

## 网站功能

- **温馨首页**：展示家庭介绍、欢迎内容和兴趣卡片；家长可编辑网站名称、文案、卡片、页脚，以及主视觉表情或头像。
- **兴趣角和音乐播放器**：访客可以浏览已发布的图片、视频、音频和在线曲目。家长可上传媒体，或搜索曲目并加入兴趣卡片；支持自动读取歌曲封面。
- **成长日记**：家长可记录日期、年龄阶段、标题和成长故事；访客可按日期或年龄阶段浏览。
- **照片与视频相册**：每条成长记录可附加多张照片和视频，支持翻页和放大查看。
- **家长管理与备份**：管理首页内容、兴趣卡片、成长记录和音乐音源，并下载或恢复完整家庭数据备份。
- **跨设备访问**：网站数据保存在服务器，同一网站地址可供家庭的多台设备访问。

## 部署

`outputs/family-site/` 是唯一目录，始终保存最新源码和部署文件。生成 ZIP 时，在仓库根目录运行：

```powershell
python scripts/package_site.py
```

默认生成 `outputs/family-site.zip`，内容直接来自 `outputs/family-site/`；不会再生成第二份部署文件夹。每次运行都重新读取该目录中的全部最新文件。需要带版本号的 ZIP 时，可指定名称，例如：

```powershell
python scripts/package_site.py --name family-site-v2026.10.15.5
```

把生成的 ZIP 上传到 Ubuntu 服务器并解压到服务器部署目录。以下统一以 `/opt/family-site` 为例；如果你选择其他目录，请将命令中的这个路径统一替换成自己的目录。然后运行一键安装脚本：

```bash
cd /opt/family-site
bash install-ubuntu.sh
```

脚本会检查 Docker Engine 和 Docker Compose 插件，必要时询问是否安装，然后构建并启动网站。默认通过服务器的 `8000` 端口访问。首次打开网站时，按页面提示创建家长账号。

如果服务器已安装 Docker 和 Compose 插件，也可手动启动：

```bash
cd /opt/family-site
mkdir -p data
sudo chown 10001:10001 data
docker compose up -d --build
```

常用维护命令：

```bash
docker compose ps          # 查看运行状态
docker compose logs -f     # 查看运行日志
docker compose down        # 停止服务，保留家庭数据
docker compose up -d --build  # 更新源码后重新构建并启动
```

服务器数据库、上传媒体和备份保存在 `/opt/family-site/data/`。升级时用新包覆盖程序文件，并保留服务器已有的 `data/` 和 `.env`；重建容器时数据也会保留。请定期备份，也不要执行会删除数据卷的清理命令。公网访问前请配置 HTTPS 反向代理，并在 `/opt/family-site/.env` 中将 `COOKIE_SECURE` 设为 `1`。完整安装、迁移、备份和安全说明见 [`outputs/family-site/README.md`](outputs/family-site/README.md)。

## 在线音乐音源

在线音乐服务随 Docker Compose 一起部署，无需另行安装插件。Compose 会自动启动内部的 `meting-api` 服务；该服务只供网站容器访问，不会把它的端口暴露到公网。

部署后登录家长账号，打开“编辑网站”→“音乐音源”，添加并测试音源：

| 配置项 | 填写内容 |
| --- | --- |
| API 地址 | `http://meting-api/api` |
| 平台代码 | `netease` 或 `tencent` |
| 鉴权方式 | `Meting-API HMAC-SHA1` |
| 服务密钥 | 默认是 `token`；若在 `.env` 设置了 `METING_TOKEN`，这里必须填写相同值 |

测试连接成功后，可在兴趣卡片中搜索并添加歌曲。歌曲封面由音源返回，访客可在网站播放器中播放；浏览器直接读取音源提供的 HTTPS 音频地址，网站服务器不转发音频。可播放曲目受音源服务和平台限制影响。

## 本地预览

需要 Python 3.10 或更新版本：

```powershell
python outputs/family-site/server.py
```

然后访问 `http://127.0.0.1:8000`。本地运行会在 `outputs/family-site/data/` 保存数据库和媒体文件。

## 仓库目录

- `outputs/family-site/`：唯一的最新网站源码、Docker 配置和安装脚本。
- `docs/superpowers/specs/`、`docs/superpowers/plans/`：功能设计与实施计划。
- `outputs/family-site.zip`：由打包脚本从 `outputs/family-site/` 生成的部署包，不纳入 Git。

家庭数据库、上传媒体、密钥和服务器备份不应提交到公开仓库。部署目录和数据迁移细节见 [`outputs/family-site/README.md`](outputs/family-site/README.md)。

## 后续规划

后续计划增加“学习兴趣工作台”，用于集中整理和展示学习内容、兴趣项目与成长记录，并发布对应的微信小程序。小程序将作为网站的另一个使用入口，与网站共用同一套家庭数据和后端服务，通过版本化 API 和统一的身份验证读取或更新内容，避免两端数据分开维护。该部分仍在规划中，尚未上线。

