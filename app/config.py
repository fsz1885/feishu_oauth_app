from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv


load_dotenv()


@dataclass
class Settings:
    """Application settings loaded from environment variables."""

    app_id: str = os.getenv("FEISHU_APP_ID", "")
    app_secret: str = os.getenv("FEISHU_APP_SECRET", "")
    redirect_uri: str = os.getenv("FEISHU_REDIRECT_URI", "http://localhost:8080/callback")
    host: str = os.getenv("APP_HOST", "0.0.0.0")
    port: int = int(os.getenv("APP_PORT", "8080"))
    debug: bool = os.getenv("APP_DEBUG", "false").lower() == "true"
    store_path: str = os.getenv("LOCAL_STORE_PATH", "data/auth_store.json")
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    requested_scopes: List[str] = field(
        default_factory=lambda: [
            # 用户身份与 OAuth 基础能力
            "auth:user.id:read",
            "offline_access",
            # 云文档搜索
            "drive:drive.search:readonly",
            "docx:document:readonly",
            "docx:document:create",
            "docx:document:write_only",
            # 获取基础用户信息（更丰富字段依赖额外权限）
            "contact:user.base:readonly",
        ]
    )

    auth_url: str = "https://accounts.feishu.cn/open-apis/authen/v1/authorize"
    token_url: str = "https://open.feishu.cn/open-apis/authen/v2/oauth/token"
    refresh_token_url: str = "https://open.feishu.cn/open-apis/authen/v2/oauth/token"
    user_info_url: str = "https://open.feishu.cn/open-apis/authen/v1/user_info"
    search_url: str = "https://open.feishu.cn/open-apis/suite/docs-api/search/object"
    docx_url: str = "https://open.feishu.cn/open-apis/docx/v1/documents"
    tenant_access_token_url: str = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    contact_scope_url: str = "https://open.feishu.cn/open-apis/contact/v3/scopes"
    contact_department_users_url: str = "https://open.feishu.cn/open-apis/contact/v3/users/find_by_department"
    contact_user_url: str = "https://open.feishu.cn/open-apis/contact/v3/users"
    contact_department_url: str = "https://open.feishu.cn/open-apis/contact/v3/departments"
    send_message_url: str = "https://open.feishu.cn/open-apis/im/v1/messages"

    @property
    def scope_string(self) -> str:
        return " ".join(self.requested_scopes)

    def validate(self) -> None:
        if not self.app_id:
            raise ValueError("缺少环境变量 FEISHU_APP_ID")
        if not self.app_secret:
            raise ValueError("缺少环境变量 FEISHU_APP_SECRET")
