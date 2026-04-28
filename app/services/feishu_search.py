from __future__ import annotations

from typing import Dict, List, Optional

import requests

from app.config import Settings


class FeishuSearchService:
    """Cloud document search service."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def search_docs(
        self,
        *,
        access_token: str,
        keyword: str,
        docs_types: Optional[List[str]] = None,
        owner_ids: Optional[List[str]] = None,
        chat_ids: Optional[List[str]] = None,
        count: int = 50,
        max_pages: int = 4,
    ) -> List[Dict]:
        all_files: List[Dict] = []
        offset = 0
        count = max(0, min(count, 50))

        for _ in range(max_pages):
            current_count = min(count, 199 - offset)
            if current_count <= 0:
                break

            body: Dict = {
                "search_key": keyword,
                "count": current_count,
                "offset": offset,
            }
            if docs_types:
                body["docs_types"] = docs_types
            if owner_ids:
                body["owner_ids"] = owner_ids
            if chat_ids:
                body["chat_ids"] = chat_ids

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=utf-8",
            }
            resp = requests.post(self.settings.search_url, headers=headers, json=body, timeout=30)
            try:
                result = resp.json()
            except ValueError:
                raise RuntimeError(f"搜索接口返回非 JSON：HTTP={resp.status_code}, body={resp.text}")
            if resp.status_code != 200 or result.get("code") != 0:
                raise RuntimeError(f"搜索失败：HTTP={resp.status_code}, result={result}")

            data = result.get("data", {})
            files = data.get("docs_entities", [])
            has_more = data.get("has_more", False)
            all_files.extend(files)

            if not has_more or not files:
                break

            offset += current_count
            if offset >= 199:
                break

        return all_files
