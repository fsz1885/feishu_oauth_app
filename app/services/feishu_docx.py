from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import requests

from app.config import Settings
from app.utils.feishu_http import request_json_with_backoff


class FeishuDocxService:
    """Read a docx document and recreate its plain text in another folder."""

    MAX_BLOCKS_PER_REQUEST = 50
    MAX_TEXT_CHARS_PER_BLOCK = 1800

    def __init__(self, settings: Settings):
        self.settings = settings

    def clone_plain_text(
        self,
        *,
        access_token: str,
        source_document_id: str,
        target_folder_token: str,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        raw_content = self.get_raw_content(access_token, source_document_id)
        new_document = self.create_document(
            access_token=access_token,
            target_folder_token=target_folder_token,
            title=title or "Copied document",
        )
        new_document_id = new_document["document_id"]
        blocks = self._content_to_text_blocks(raw_content)
        inserted_blocks = self.append_blocks(access_token, new_document_id, blocks)

        return {
            "source_document_id": source_document_id,
            "target_folder_token": target_folder_token,
            "new_document_id": new_document_id,
            "new_document": new_document,
            "raw_content_length": len(raw_content),
            "created_block_count": len(inserted_blocks),
        }

    def get_raw_content(self, access_token: str, document_id: str) -> str:
        result = self._request_json(
            "get",
            f"{self.settings.docx_url}/{document_id}/raw_content",
            access_token=access_token,
        )
        data = result.get("data", {}) or {}
        content = data.get("content")
        if content is None:
            content = data.get("raw_content")
        return str(content or "")

    def extract_minutes_meta(
        self,
        *,
        access_token: str,
        document_id: str,
        user_name: str,
    ) -> Dict[str, Any]:
        """Extract metadata from a Feishu Minutes (妙记) docx and suggest a filename.

        Returns fields like recording_time, theme, and suggested_filename.
        """
        content = self.get_raw_content(access_token, document_id)

        # 录音时间：2026年5月17日（周日） 16:47 - 17:06 （GMT+08）
        time_match = re.search(
            r"录音时间[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日"
            r"[（(]([^)）]+)[)）]\s*(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})"
            r"(?:\s*[（(]([^)）]+)[)）])?",
            content,
        )

        # 录音主题：金地楼盘销售信息介绍与讨论
        theme_match = re.search(r"录音主题[：:]\s*(.+)", content)

        # 文字记录标题（第一行）
        title_match = re.search(r"文字记录[：:]\s*(.+)", content)

        meta: Dict[str, Any] = {
            "document_id": document_id,
            "has_recording_time": bool(time_match),
            "has_theme": bool(theme_match),
            "has_title": bool(title_match),
        }

        if time_match:
            year, month, day, weekday, start_time, end_time, timezone = time_match.groups()
            formatted_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            meta["recording_time"] = {
                "raw": time_match.group(0).split("\n")[0].strip(),
                "date": formatted_date,
                "weekday": weekday,
                "start_time": start_time,
                "end_time": end_time,
                "timezone": timezone or "GMT+08",
            }
            safe_name = re.sub(r'[\\/:*?"<>|]', "_", user_name).strip() or "未知用户"
            meta["suggested_filename"] = f"{safe_name} {formatted_date} {start_time}"
        else:
            meta["recording_time"] = None
            meta["suggested_filename"] = None

        if theme_match:
            meta["theme"] = theme_match.group(1).strip()
        else:
            meta["theme"] = None

        if title_match:
            meta["title"] = title_match.group(1).strip()
        else:
            meta["title"] = None

        return meta

    def create_document(
        self,
        *,
        access_token: str,
        target_folder_token: str,
        title: str,
    ) -> Dict[str, Any]:
        result = self._request_json(
            "post",
            self.settings.docx_url,
            access_token=access_token,
            json_body={
                "folder_token": target_folder_token,
                "title": title,
            },
        )
        data = result.get("data", {}) or {}
        document = data.get("document") or data
        document_id = document.get("document_id") or data.get("document_id")
        if not document_id:
            raise RuntimeError(f"Create document response did not include document_id: {result}")
        return {
            **document,
            "document_id": document_id,
        }

    def append_blocks(
        self,
        access_token: str,
        document_id: str,
        blocks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        inserted: List[Dict[str, Any]] = []
        if not blocks:
            return inserted

        url = f"{self.settings.docx_url}/{document_id}/blocks/{document_id}/children"
        for start in range(0, len(blocks), self.MAX_BLOCKS_PER_REQUEST):
            chunk = blocks[start:start + self.MAX_BLOCKS_PER_REQUEST]
            result = self._request_json(
                "post",
                url,
                access_token=access_token,
                params={"document_revision_id": "-1"},
                json_body={
                    "index": -1,
                    "children": chunk,
                },
            )
            data = result.get("data", {}) or {}
            inserted.extend(data.get("children") or data.get("blocks") or [])
        return inserted

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        access_token: str,
        json_body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        resp = request_json_with_backoff(
            method,
            url,
            headers=headers,
            json_body=json_body,
            params=params,
            timeout=30,
        )
        try:
            result = resp.json()
        except ValueError:
            raise RuntimeError(f"Feishu docx request returned non-JSON: HTTP={resp.status_code}, body={resp.text}")

        if resp.status_code != 200 or result.get("code") != 0:
            raise RuntimeError(f"Feishu docx request failed: HTTP={resp.status_code}, result={result}")
        return result

    def _content_to_text_blocks(self, content: str) -> List[Dict[str, Any]]:
        if not content:
            return []

        blocks: List[Dict[str, Any]] = []
        for paragraph in content.splitlines():
            text = paragraph if paragraph else " "
            for chunk in self._split_text(text, self.MAX_TEXT_CHARS_PER_BLOCK):
                blocks.append({
                    "block_type": 2,
                    "text": {
                        "elements": [
                            {
                                "text_run": {
                                    "content": chunk,
                                },
                            },
                        ],
                    },
                })
        return blocks

    @staticmethod
    def _split_text(text: str, max_chars: int) -> List[str]:
        return [text[i:i + max_chars] for i in range(0, len(text), max_chars)] or [" "]
