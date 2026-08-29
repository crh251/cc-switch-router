# cc-switch-router

给 [farion1231/cc-switch](https://github.com/farion1231/cc-switch) 打「按终端路由」补丁，并用 GitHub Actions 自动构建 macOS（Apple Silicon）DMG。

> 本仓库只包含**按版本划分的补丁文件**与构建流水线，不含 cc-switch 源码；构建时按所选版本自动拉取上游源码并套用对应补丁。

## 仓库结构与原理

```
├── patches/
│   └── v3.20.1.patch               # 针对上游 v3.20.1 tag 的标准 diff（git apply 可干净套用）
└── .github/workflows/build-macos.yml
```

workflow 流程：下载所选版本的上游源码 tarball → `git apply patches/<所选版本>.patch` → `pnpm tauri build --target aarch64-apple-darwin` → `hdiutil` 打包 DMG → 发布到本仓库 Release。

补丁的三处修改：

1. `provider_router.rs`：新增 `select_provider_by_override()` —— 按请求头指定的名字/ID 显式选择供应商
2. `handler_context.rs`：读 `x-ccs-provider` 请求头，命中则该请求固定路由到指定供应商（跳过全局"当前供应商"与故障转移），未命中回退
3. `tauri.conf.json`：`createUpdaterArtifacts: false` + 删除 `plugins.updater`（自编译无需签名 key；防止官方更新覆盖补丁版）

每个版本的补丁都是对**该版本源码**生成的标准 diff，因此旧版本随时可以重新构建，永远能干净套用。

## 构建

GitHub → **Actions** → **Build macOS arm64 (patched cc-switch)** → **Run workflow** → 下拉选择 cc-switch 版本 → Run

构建完成后在本仓库 **Releases** 下载 `CC-Switch-<版本>-macos-arm64-ccs.dmg`。

## 安装

DMG 未签名。浏览器下载时会给 DMG 打隔离标记，**先清除再挂载**，否则 app 会报「已损坏」：

```bash
xattr -d com.apple.quarantine ~/Downloads/CC-Switch-<版本>-macos-arm64-ccs.dmg
open ~/Downloads/CC-Switch-<版本>-macos-arm64-ccs.dmg
# 打开窗口里把 CC Switch Router.app 拖到 Applications 快捷方式（或手动拷贝替换）
```

> 应用名为 **CC Switch Router**，可与官方 CC Switch 共存区分；但两者共用 `~/.cc-switch` 数据且同一时间只能运行一个（同一应用锁）。

## 终端用法（ccs 脚本）

app 每次启动会自动把内置的 `ccs` 脚本安装到 `~/script/bin`（你已加入 PATH）。已开着的终端跑一次 `rehash`，或新开终端即可：

```bash
ccs                    # 官方直连（api.anthropic.com，不经本地路由）
ccs kimi               # 走本地路由 → Kimi（该终端固定）
ccs openrouter         # 走本地路由 → OpenRouter
ccs glm-router         # 走本地路由 → GLM 标准端点（协议转换自动完成）
ccs kimi -c            # 供应商名后面的参数原样透传给 claude
ccs help
```

- 供应商名 = cc-switch 界面里的名字，**不区分大小写、支持部分匹配**（`ccs glm` 可匹配 glm-router）
- 依赖：CC Switch Router 运行中且已开启路由接管（启动前脚本会预检 15721 端口）
- 手动安装（可选）：`install -m 755 ccs ~/script/bin/ccs`

不用 ccs 的手动方式（等价）：`claude --settings` 传入带 `ANTHROPIC_CUSTOM_HEADERS: "x-ccs-provider: <名字>"` 的 env 覆盖即可。

## 新增支持的版本

1. 下载新版本源码，重新应用同样的三处修改，导出 `patches/<新版本>.patch`（若上游这两处代码没变，直接复用旧补丁内容改个名也可以）
2. `.github/workflows/build-macos.yml` 的 `options:` 列表加一行
3. 提交推送后，Actions 里即可选到新版本
