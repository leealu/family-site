#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

if ! command -v apt-get >/dev/null 2>&1; then
  echo "此安装脚本适用于 Ubuntu。其他系统请使用 Docker Compose 手动部署。" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo "需要安装 Docker Engine 和 Compose 插件。将通过 Docker 官方 Ubuntu 软件源安装。"
  read -r -p "现在安装 Docker 吗？[y/N] " answer
  case "$answer" in y|Y|yes|YES) ;; *) echo "已取消。先安装 Docker Engine 与 Compose 插件，再重新运行本脚本。"; exit 1;; esac

  sudo apt-get update
  sudo apt-get install -y ca-certificates curl
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  codename="${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}"
  if [[ -z "$codename" ]]; then echo "无法识别 Ubuntu 版本代号。" >&2; exit 1; fi
  arch="$(dpkg --print-architecture)"
  printf 'Types: deb\nURIs: https://download.docker.com/linux/ubuntu\nSuites: %s\nComponents: stable\nArchitectures: %s\nSigned-By: /etc/apt/keyrings/docker.asc\n' "$codename" "$arch" | sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo systemctl enable --now docker
fi

if ! docker info >/dev/null 2>&1; then
  sudo systemctl enable --now docker
  DOCKER=(sudo docker)
else
  DOCKER=(docker)
fi

if [[ ! -f .env ]]; then
  cat > .env <<'EOF'
SITE_PORT=8000
COOKIE_SECURE=0
EOF
  chmod 600 .env
fi

mkdir -p data
if ! chown 10001:10001 data 2>/dev/null; then sudo chown 10001:10001 data; fi

"${DOCKER[@]}" compose up -d --build

port="$(sed -n 's/^SITE_PORT=//p' .env | tail -n 1)"
port="${port:-8000}"
lan_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo "芽芽的奇妙小世界已经启动。"
echo "本机访问：http://127.0.0.1:${port}"
if [[ -n "$lan_ip" ]]; then echo "同一局域网访问：http://${lan_ip}:${port}"; fi
echo "首次打开时创建家长账号。内容和媒体保存在当前目录的 data/ 文件夹中。"
echo "停止服务：${DOCKER[*]} compose down（数据会保留）"
