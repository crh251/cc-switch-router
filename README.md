# cc-switch-router

给 [farion1231/cc-switch](https://github.com/farion1231/cc-switch) 打「按终端路由」补丁，并用 GitHub Actions 自动构建 macOS（Apple Silicon）DMG。

> 本仓库只包含补丁与构建流水线，不含 cc-switch 源码；构建时按所选版本自动拉取上游源码。

## 补丁能力

给 cc-switch 本地代理（127.0.0.1:15721）增加**按请求头路由**的能力：

- Claude Code 启动时带 `ANTHROPIC_CUSTOM_HEADERS: "x-ccs-provider: <供应商名>"`
- 代理收到带此头的请求，固定路由到指定供应商（跳过全局"当前供应商"与故障转移）
- 不带头的请求行为与官方版完全一致（走全局当前供应商）
- 效果：多个终端同时各用各的供应商，互不影响

## 构建

GitHub → **Actions** → **Build macOS arm64 (patched cc-switch)** → **Run workflow** → 选择 cc-switch 版本 → Run

> 仅支持 options 列表中已适配补丁的版本。

构建完成后在本仓库 **Releases** 下载 `CC-Switch-<版本>-macos-arm64-ccs.dmg`。

## 安装

DMG 未签名，首次打开前去掉隔离属性：

```bash
hdiutil attach CC-Switch-<版本>-macos-arm64-ccs.dmg
xattr -cr "/Volumes/CC Switch/CC Switch.app"
# 拷贝到目标位置替换旧版（供应商数据在 ~/.cc-switch，不受影响）
```

## 终端用法

每供应商一个 profile（如 `~/.claude/profiles/kimi.json`），启动时 `--settings` 指定：

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:15721",
    "ANTHROPIC_AUTH_TOKEN": "PROXY_MANAGED",
    "ANTHROPIC_CUSTOM_HEADERS": "x-ccs-provider: kimi",
    "ANTHROPIC_MODEL": "kimi-k2.7-code",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "kimi-k2.7-code",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "kimi-k2.7-code",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "kimi-k2.7-code",
    "CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT": "1"
  }
}
```

```bash
claude --settings ~/.claude/profiles/kimi.json        # 该终端永远走 Kimi
```

- 不同终端用不同 profile → 各走各的供应商，并行互不影响
- 不带 `--settings` 的终端 → 走 cc-switch 全局当前供应商
- `x-ccs-provider` 的值 = cc-switch 里的供应商名字（忽略大小写）或 id

## 新增支持的版本

1. 获取对应版本的源码，基于它重新生成 `patches/<版本>.patch`（改动内容：`provider_router.rs` 按头路由 + 单测、`handler_context.rs` 读头、`tauri.conf.json` 禁用更新器）
2. `.github/workflows/build-macos.yml` 的 `options:` 列表加一行
3. 提交推送后，Actions 里即可选到新版本
