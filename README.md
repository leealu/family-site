# 家庭成长记录网站

这是一个可在 Ubuntu/Docker 上运行的家庭成长记录网站。

## 项目结构

- `outputs/site/`：网站唯一的可维护源码，包括 Python 后端、前端资源和 Docker/安装文件。
- `docs/superpowers/specs/`：经讨论形成的功能设计说明。
- `docs/superpowers/plans/`：经确认后的实施计划。
- `outputs/family-site/` 和 `outputs/family-site.zip`：可重新生成的部署副本，不纳入 Git。

## 本地预览

需要 Python 3.10 或更新版本：

```powershell
cd outputs/site
python server.py
```

浏览器访问 `http://127.0.0.1:8000`。

## Docker 部署

在服务器将 `outputs/site/` 复制到部署目录后，运行：

```sh
docker compose up -d --build
```

部署数据保存在 `data/`，包括家庭数据库和上传媒体。升级源码时不要删除或覆盖服务器上的 `data/`。运行数据、密钥和上传的儿童照片/视频已通过 `.gitignore` 排除；不要将这些内容提交到 Git 仓库。

具体安装和备份方式见 [`outputs/site/README.md`](outputs/site/README.md)。

