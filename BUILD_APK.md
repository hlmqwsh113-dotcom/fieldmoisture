# 打包 APK 指南

buildozer 只能在 Linux 上运行（Windows 不支持）。推荐顺序：**GitHub Actions（零安装）> WSL2 > Docker**。

## 关于签名（本机自用无需任何证书）

Android 规定所有 APK 必须带签名才能安装，但**自用不需要自己申请/创建证书**：

- 本指南所有方式生成的都是 **debug 包**，buildozer 用内置调试密钥**自动签名**，全程无感知；
- 手机上只需打开"允许安装未知来源应用"即可直接安装；
- 不需要密钥库（keystore）、不需要签名密码、GitHub 仓库也不用配任何 Secrets；
- 只有要上架应用商店时才需要正式的 release 签名，本场景用不到。

## 方式一：GitHub Actions 云端打包（电脑零安装）

项目已自带工作流 `.github/workflows/build-apk.yml`，本地 git 仓库也已初始化并提交完毕。
只剩两步（需要你的 GitHub 账号）：

**第 1 步**：浏览器打开 https://github.com/new ，仓库名填 `fieldmoisture`（私有/公开均可），
**不要**勾选"Add a README"，点 Create repository。

**第 2 步**：在 moisture-app 目录执行（把 `<你的用户名>` 换成 GitHub 用户名）：

```bash
cd "C:\Users\hlwsh\WorkBuddy\2026-10-08-06-12-32\moisture-app"
git remote add origin https://github.com/<你的用户名>/fieldmoisture.git
git push -u origin main
```

> 首次 push 会弹出登录窗口，用浏览器授权即可；如果提示输密码，
> 需要用 Personal Access Token（GitHub → Settings → Developer settings → Tokens）。

push 后自动开始构建：GitHub 仓库页 → **Actions** → 等构建完成（首次约 30-40 分钟，
之后有缓存约 10 分钟）→ 点进构建记录 → 底部 **Artifacts** 下载 `fieldmoisture-apk`，
解压得到 `.apk`，传到手机安装。

> 也可以在 Actions 页面手动点 **Run workflow** 触发，不用每次 push。
> 生成的是 debug 包（自动签名，无需证书），可直接安装。手机需允许"安装未知来源应用"。

## 方式二：WSL2（Windows 本地打包）

**一键方式（推荐）**：双击项目根目录的 **`build-apk.bat`** 即可。它会自动：
检查/安装 Ubuntu（WSL）→ 安装编译依赖 → 在 Linux 文件系统里编译 → 把 APK 拷回 `bin\` 目录。
首次运行需下载 Android SDK/NDK 约 3GB（30-60 分钟），期间不要关窗口。产物为 debug 包（自动签名，无需证书）。

手动方式（等价于 bat 里的步骤）：

1. 管理员 PowerShell 执行 `wsl --install`，重启后设置 Ubuntu 用户名密码
2. 在 WSL 终端执行：

```bash
sudo apt update && sudo apt install -y git zip unzip openjdk-17-jdk python3-pip \
  autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev \
  libtinfo5 cmake libffi-dev libssl-dev
pip3 install buildozer cython
# 建议拷到 Linux 文件系统再编译（/mnt/c 上编译慢且易出错）：
cp -r /mnt/c/Users/hlwsh/WorkBuddy/2026-10-08-06-12-32/moisture-app ~/moisture-app
cd ~/moisture-app && buildozer android debug
```

产物：`bin/fieldmoisture-1.0-arm64-v8a-debug.apk`。

## 方式三：Docker

```bash
cd moisture-app
docker run --rm -v %cd%:/home/user/hostcwd kivy/buildozer android debug
```

## 打包配置说明（buildozer.spec 已配好）

| 配置项 | 值 | 说明 |
|---|---|---|
| title | 田间水分采集 | 应用名 |
| requirements | python3, kivy==2.3.0, openpyxl | 依赖 |
| android.permissions | READ/WRITE_EXTERNAL_STORAGE | 读写手机存储里的 Excel |
| android.minapi / api | 23 / 34 | 支持 Android 6.0+ |
| android.archs | arm64-v8a, armeabi-v7a | 覆盖主流机型 |
| source.include_exts | py,xlsx,ttf | 打包中文字体等 |

## 手机端数据文件夹

App 首次启动自动创建专属文件夹（文件管理器可见）：

```
手机存储/田间水分采集/          ← 把 .xlsx 表格拷到这里，导入的表也集中存这里
手机存储/田间水分采集/导出/      ← “导出数据”生成的带时间戳副本
```

安卓 11+ 若无共享存储权限，自动回退到 `Android/data/org.field.fieldmoisture/files/田间水分采集/`（免权限，文件管理器同样可见）。
