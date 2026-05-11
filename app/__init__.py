from __future__ import annotations

from flask import Flask

from app.config import Settings
from app.routes import auth_bp, docx_bp, search_bp
from app.services.feishu_docx import FeishuDocxService
from app.services.feishu_invite import FeishuInviteService
from app.services.feishu_oauth import FeishuOAuthService
from app.services.feishu_search import FeishuSearchService
from app.storage.json_store import LocalAuthStore


def create_app() -> Flask:
    settings = Settings()
    settings.validate()

    app = Flask(__name__)
    app.config["REQUESTED_SCOPE_STRING"] = settings.scope_string

    store = LocalAuthStore(settings.store_path)
    oauth_service = FeishuOAuthService(settings, store)
    search_service = FeishuSearchService(settings)
    docx_service = FeishuDocxService(settings)
    invite_service = FeishuInviteService(settings)

    app.extensions["settings"] = settings
    app.extensions["store"] = store
    app.extensions["oauth_service"] = oauth_service
    app.extensions["search_service"] = search_service
    app.extensions["docx_service"] = docx_service
    app.extensions["invite_service"] = invite_service

    app.register_blueprint(auth_bp)
    app.register_blueprint(docx_bp)
    app.register_blueprint(search_bp)
    invite_service.start_contact_cache_scheduler()
    return app
