#!/usr/bin/env python3
"""对 cc-switch v3.20.1 源码应用「x-ccs-provider 按头路由」修改。

用法：python3 patch_ccs.py <cc-switch 源码目录>
每处修改都要求精确匹配原文且只出现一次；匹配失败立即报错退出，不会产生半套用状态。
"""

import pathlib
import sys

if len(sys.argv) != 2:
    print("用法: python3 patch_ccs.py <cc-switch 源码目录>")
    sys.exit(1)
root = pathlib.Path(sys.argv[1])
if not (root / "src-tauri" / "tauri.conf.json").exists():
    print(f"[FAIL] {root} 不像 cc-switch 源码目录（缺 src-tauri/tauri.conf.json）")
    sys.exit(1)


def patch_file(rel, replacements):
    p = root / rel
    s = p.read_text(encoding="utf-8")
    for i, (old, new) in enumerate(replacements, 1):
        n = s.count(old)
        if n != 1:
            print(f"[FAIL] {rel} 第{i}处修改：原文片段出现 {n} 次（期望 1 次）：{old[:60]!r}...")
            sys.exit(1)
        s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")
    print(f"[OK] {rel}（{len(replacements)} 处修改）")


# ── 1) provider_router.rs：新增 select_provider_by_override ──────────────
patch_file(
    "src-tauri/src/proxy/provider_router.rs",
    [
        (
            """        Ok(result)
    }

    /// 请求执行前获取熔断器“放行许可”""",
            """        Ok(result)
    }

    /// 按显式覆盖（`x-ccs-provider` 请求头）选择供应商
    ///
    /// 在该应用的全部供应商中按名字（忽略大小写）或 id 匹配；命中返回单个供应商
    /// （显式指定不参与故障转移与熔断检查），未命中返回 `None`，由调用方回退默认逻辑。
    pub async fn select_provider_by_override(
        &self,
        app_type: &str,
        override_ref: &str,
    ) -> Result<Option<Provider>, AppError> {
        let all_providers = self.db.get_all_providers(app_type)?;
        let hit = all_providers.values().find(|provider| {
            provider.name.eq_ignore_ascii_case(override_ref) || provider.id == override_ref
        });
        Ok(hit.cloned())
    }

    /// 请求执行前获取熔断器“放行许可”""",
        )
    ],
)

# ── 2) handler_context.rs：读 x-ccs-provider 请求头路由 ──────────────────
patch_file(
    "src-tauri/src/proxy/handler_context.rs",
    [
        (
            """        // 使用共享的 ProviderRouter 选择 Provider（熔断器状态跨请求保持）
        // 注意：只在这里调用一次，结果传递给 forwarder，避免重复消耗 HalfOpen 名额
        let providers = state
            .provider_router
            .select_providers(app_type_str)
            .await
            .map_err(|e| match e {
                crate::error::AppError::AllProvidersCircuitOpen => {
                    ProxyError::AllProvidersCircuitOpen
                }
                crate::error::AppError::NoProvidersConfigured => ProxyError::NoProvidersConfigured,
                _ => ProxyError::DatabaseError(e.to_string()),
            })?;""",
            """        // 使用共享的 ProviderRouter 选择 Provider（熔断器状态跨请求保持）
        // 注意：只在这里调用一次，结果传递给 forwarder，避免重复消耗 HalfOpen 名额
        //
        // ccs 扩展：请求头 `x-ccs-provider: <供应商名|id>` 显式指定供应商（终端级隔离），
        // 命中时跳过当前供应商与故障转移；未命中或不带头时走默认选择逻辑。
        let ccs_provider_override = headers
            .get("x-ccs-provider")
            .and_then(|value| value.to_str().ok())
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .map(str::to_string);

        let providers_result = if let Some(override_ref) = ccs_provider_override.as_deref() {
            match state
                .provider_router
                .select_provider_by_override(app_type_str, override_ref)
                .await
            {
                Ok(Some(provider)) => {
                    log::info!(
                        "[{}] [ccs] x-ccs-provider 命中: {} ({}), model: {}",
                        tag,
                        provider.name,
                        provider.id,
                        request_model
                    );
                    Ok(vec![provider])
                }
                Ok(None) => {
                    log::warn!(
                        "[{}] [ccs] x-ccs-provider '{override_ref}' 未匹配任何供应商，回退默认选择",
                        tag
                    );
                    state.provider_router.select_providers(app_type_str).await
                }
                Err(e) => Err(e),
            }
        } else {
            state
                .provider_router
                .select_providers(app_type_str)
                .await
        };

        let providers = providers_result.map_err(|e| match e {
            crate::error::AppError::AllProvidersCircuitOpen => ProxyError::AllProvidersCircuitOpen,
            crate::error::AppError::NoProvidersConfigured => ProxyError::NoProvidersConfigured,
            _ => ProxyError::DatabaseError(e.to_string()),
        })?;""",
        )
    ],
)

# ── 3) tauri.conf.json：禁用更新器 artifact（自编译无需签名 key）────────────
patch_file(
    "src-tauri/tauri.conf.json",
    [
        ('    "createUpdaterArtifacts": true,', '    "createUpdaterArtifacts": false,')
    ],
)

# ── 4) tauri.conf.json：移除 updater 插件配置（防官方更新覆盖补丁版）────────
conf = "src-tauri/tauri.conf.json"
p = root / conf
s = p.read_text(encoding="utf-8")
old = """    },
    "updater": {
      "pubkey": "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IEM4MDI4QzlBNTczOTI4RTMKUldUaktEbFhtb3dDeUM5US9kT0FmdGR5Ti9vQzcwa2dTMlpibDVDUmQ2M0VGTzVOWnd0SGpFVlEK",
      "endpoints": [
        "https://dl.ccswitch.io/latest.json",
        "https://github.com/farion1231/cc-switch/releases/latest/download/latest.json"
      ]
    }
  }"""
new = """    }
  }"""
n = s.count(old)
if n != 1:
    print(f"[FAIL] {conf}: updater 配置块出现 {n} 次（期望 1 次）")
    sys.exit(1)
p.write_text(s.replace(old, new, 1), encoding="utf-8")
print(f"[OK] {conf}（updater 配置已移除）")

print("全部修改应用完成 ✓")
