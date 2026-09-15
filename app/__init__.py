from __future__ import annotations

from flask import Flask

from app.config import Settings
from app.routes import auth_bp, capture_bp, docx_bp, search_bp
from app.services.content_capture import ContentCaptureService
from app.services.feishu_docx import FeishuDocxService
from app.services.feishu_invite import FeishuInviteService
from app.services.feishu_oauth import FeishuOAuthService
from app.services.feishu_search import FeishuSearchService
from app.storage.capture_store import CaptureStore
from app.storage.json_store import LocalAuthStore


def create_app() -> Flask:
    settings = Settings()
    settings.validate()

    app = Flask(__name__)
    app.secret_key = settings.session_secret_key
    app.config["REQUESTED_SCOPE_STRING"] = settings.scope_string

    store = LocalAuthStore(settings.store_path)
    capture_store = CaptureStore(settings.capture_store_path)
    oauth_service = FeishuOAuthService(settings, store)
    search_service = FeishuSearchService(settings)
    docx_service = FeishuDocxService(settings)
    invite_service = FeishuInviteService(settings)
    capture_service = ContentCaptureService(
        settings=settings,
        capture_store=capture_store,
        oauth_service=oauth_service,
        search_service=search_service,
        docx_service=docx_service,
    )

    app.extensions["settings"] = settings
    app.extensions["store"] = store
    app.extensions["capture_store"] = capture_store
    app.extensions["oauth_service"] = oauth_service
    app.extensions["search_service"] = search_service
    app.extensions["docx_service"] = docx_service
    app.extensions["invite_service"] = invite_service
    app.extensions["capture_service"] = capture_service

    app.register_blueprint(auth_bp)
    app.register_blueprint(capture_bp)
    app.register_blueprint(docx_bp)
    app.register_blueprint(search_bp)
    invite_service.start_contact_cache_scheduler()
    oauth_service.start_token_refresh_scheduler()
    capture_service.start_scheduler()
    return app
