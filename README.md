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

补丁的八处修改：

1. `provider_router.rs`：新增 `select_provider_by_override()` —— 按请求头指定的名字/ID 显式选择供应商
2. `handler_context.rs`：读 `x-ccs-provider` 请求头，命中则该请求固定路由到指定供应商（跳过全局"当前供应商"与故障转移），未命中回退；新增 Auto Mode 安全分类器审查官方直连旁路拦截
3. `safety_bypass.rs`：新增安全分类器审查识别与 macOS Keychain（`Claude Code-credentials`）官方 Token 读取与 5 分钟缓存
4. `tauri.conf.json`：`createUpdaterArtifacts: false` + 删除 `plugins.updater`（自编译无需签名 key；防止官方更新覆盖补丁版）
5. 错误请求行也按「实际发出的请求」归因模型映射：`forwarder.rs` 新增 `AttemptContext{outbound_model,url}`，`forward()` 出站前写入实际模型与目标 URL 并随 `ForwardError` 带回（重试/整流/故障转移各路径接线）；`handlers.rs` 的 `log_forward_error()` 改吃 `&ForwardError`，用 `err.ctx.outbound_model` 归因（请求未发出则回退、不显示映射），`usage/logger.rs` 的 `log_error_with_context()` 接受独立的 `request_model`——统计页非 2xx 的行同样显示 `请求模型 → 实际出站模型`
6. 统计表显示报错原因与目标 URL：`error_mapper.rs` 新增 `extract_upstream_error_reason()`/`get_log_error_message()`，从上游错误响应体提取可读原因（`error.message`/`message`/`base_resp.status_msg`，JSON 解析失败回退原文截断 500 字，取不到只记状态码；客户端可见的错误响应行为不变），URL 由 `log_forward_error()` 以 `（https://…）` 追加；前端 `RequestLogTable.tsx` 在状态码下方第二行显示原因，悬浮看全文，无原因不显示
7. `/model` 实时显示映射：`ccs_router.rs` 新增 `regenerate_claude_settings_files()`，在供应商增删改及启动时自动重生成 `~/.cc-switch/claude-settings/<供应商>.json`（`_MODEL`=官方档位别名、`_MODEL_NAME`=映射名，与 ccs 脚本生成格式一致；claude 对 settings 文件热加载）——ccs（默认继承模式）终端里改映射后 `/model` 实时刷新，选中即发送官方别名、由代理按关键词实时路由，全程无需重启
8. 统计表标识 Auto Mode 分类器审查请求：安全旁路会把审查请求路由到合成供应商 `claude-safety-bypass`（不在 providers 表中），`RequestLogTable.tsx` 对这类行渲染紫色「分类器审查」徽章 + Claude Official 名称，悬浮说明来源

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
