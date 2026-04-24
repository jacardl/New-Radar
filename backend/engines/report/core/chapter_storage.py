"""
ç« èJSONçè½çä¸æ¸åç®¡ç

æ¯ä¸ç« å¨æµå¼çææ¶ä¼ç«å³åå¥rawæä»¶ï¼å®ææ ¡éªåååå?
æ ¼å¼åçchapter.jsonï¼å¹¶å¨manifestä¸­è®°å½åæ°æ®ï¼ä¾¿äºåç»­è£è®¢
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Generator, List, Optional


@dataclass
class ChapterRecord:
    """
    manifestä¸­è®°å½çç« èåæ°æ®

    è¯¥ç»æç¨äºå¨ `manifest.json` ä¸­è¿½è¸ªæ¯ç« çç¶æãæä»¶ä½ç½®
    ä»¥åå¯è½çéè¯¯åè¡¨ï¼æ¹ä¾¿åç«¯æè°è¯å·¥å·è¯»å
    """

    chapter_id: str
    slug: str
    title: str
    order: int
    status: str
    files: Dict[str, str] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> Dict[str, object]:
        """å°è®°å½è½¬æ¢ä¸ºä¾¿äºåå¥manifest.jsonçåºååå­å¸"""
        return {
            "chapterId": self.chapter_id,
            "slug": self.slug,
            "title": self.title,
            "order": self.order,
            "status": self.status,
            "files": self.files,
            "errors": self.errors,
            "updatedAt": self.updated_at,
        }


class ChapterStorage:
    """
    ç« èJSONåå¥ä¸manifestç®¡çå¨

    è´è´£ï¼?
        - ä¸ºæ¯æ¬¡æ¥ååå»ºç¬ç«runç®å½ä¸manifestå¿«ç§ï¼?
        - å¨ç« èæµå¼çææ¶å³æ¶åå¥ `stream.raw`ï¼?
        - æ ¡éªéè¿åæä¹å `chapter.json` å¹¶æ´æ°manifestç¶æ
    """

    def __init__(self, base_dir: str):
        """
        åå»ºç« èå­å¨å¨

        Args:
            base_dir: ææè¾åºrunç®å½çæ ¹è·¯å¾
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._manifests: Dict[str, Dict[str, object]] = {}

    # ======== ä¼è¯ä¸æ¸å?========

    def start_session(self, report_id: str, metadata: Dict[str, object]) -> Path:
        """
        ä¸ºæ¬æ¬¡æ¥ååå»ºç¬ç«çç« èè¾åºç®å½ä¸manifest

        åæ¶æå¨å±metadataåå¥ `manifest.json`ï¼ä¾æ¸²æ/è°è¯æ¥è¯¢

        åæ°:
            report_id: ä»»å¡ID
            metadata: Reportåæ°æ®ï¼æ é¢ãä¸»é¢ç­ï¼

        è¿å:
            Path: æ°å»ºçrunç®å½
        """
        run_dir = self.base_dir / report_id
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "reportId": report_id,
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "metadata": metadata,
            "chapters": [],
        }
        self._manifests[self._key(run_dir)] = manifest
        self._write_manifest(run_dir, manifest)
        return run_dir

    def begin_chapter(self, run_dir: Path, chapter_meta: Dict[str, object]) -> Path:
        """
        åå»ºç« èå­ç®å½å¹¶å¨manifestä¸­æ è®°ä¸ºstreamingç¶æ

        ä¼çæ?`order-slug` é£æ ¼çå­ç®å½ï¼å¹¶æåç»è®° raw æä»¶è·¯å¾

        åæ°:
            run_dir: ä¼è¯æ ¹ç®å½
            chapter_meta: åå« chapterId/title/slug/order çåæ°æ®

        è¿å:
            Path: ç« èç®å½
        """
        slug_value = str(
            chapter_meta.get("slug") or chapter_meta.get("chapterId") or "section"
        )
        chapter_dir = self._chapter_dir(
            run_dir,
            slug_value,
            int(chapter_meta.get("order", 0)),
        )
        record = ChapterRecord(
            chapter_id=str(chapter_meta.get("chapterId")),
            slug=slug_value,
            title=str(chapter_meta.get("title")),
            order=int(chapter_meta.get("order", 0)),
            status="streaming",
            files={"raw": str(self._raw_stream_path(chapter_dir).relative_to(run_dir))},
        )
        self._upsert_record(run_dir, record)
        return chapter_dir

    def persist_chapter(
        self,
        run_dir: Path,
        chapter_meta: Dict[str, object],
        payload: Dict[str, object],
        errors: Optional[List[str]] = None,
    ) -> Path:
        """
        ç« èæµå¼çæå®æ¯ååå¥æç»JSONå¹¶æ´æ°manifestç¶æ

        è¥æ ¡éªå¤±è´¥ï¼éè¯¯ä¿¡æ¯ä¼è¢«åå¥manifestï¼ä¾åç«¯å±ç¤º

        åæ°:
            run_dir: ä¼è¯æ ¹ç®å½
            chapter_meta: ç« èåä¿¡æ¯
            payload: æ ¡éªéè¿çç« èJSON
            errors: å¯éçéè¯¯åè¡¨ï¼ç¨äºæ è®°invalidç¶æ

        è¿å:
            Path: æç»ç `chapter.json` æä»¶è·¯å¾
        """
        slug_value = str(
            chapter_meta.get("slug") or chapter_meta.get("chapterId") or "section"
        )
        chapter_dir = self._chapter_dir(
            run_dir,
            slug_value,
            int(chapter_meta.get("order", 0)),
        )
        final_path = chapter_dir / "chapter.json"
        final_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        record = ChapterRecord(
            chapter_id=str(chapter_meta.get("chapterId")),
            slug=slug_value,
            title=str(chapter_meta.get("title")),
            order=int(chapter_meta.get("order", 0)),
            status="ready" if not errors else "invalid",
            files={
                "raw": str(self._raw_stream_path(chapter_dir).relative_to(run_dir)),
                "json": str(final_path.relative_to(run_dir)),
            },
            errors=errors or [],
        )
        self._upsert_record(run_dir, record)
        return final_path

    def load_chapters(self, run_dir: Path) -> List[Dict[str, object]]:
        """
        ä»æå®runç®å½è¯»åå¨é¨chapter.jsonå¹¶æorderæåºè¿å

        å¸¸ç¨äº?DocumentComposer å°å¤ä¸ªç« èè£è®¢ææ´æ¬IR

        åæ°:
            run_dir: ä¼è¯æ ¹ç®å½

        è¿å:
            list[dict]: ç« èpayloadåè¡¨
        """
        payloads: List[Dict[str, object]] = []
        for child in sorted(run_dir.iterdir()):
            if not child.is_dir():
                continue
            chapter_path = child / "chapter.json"
            if not chapter_path.exists():
                continue
            try:
                payload = json.loads(chapter_path.read_text(encoding="utf-8"))
                payloads.append(payload)
            except json.JSONDecodeError:
                continue
        payloads.sort(key=lambda x: x.get("order", 0))
        return payloads

    # ======== æä»¶æä½ ========

    @contextmanager
    def capture_stream(self, chapter_dir: Path) -> Generator:
        """
        å°æµå¼è¾åºå®æ¶åå¥rawæä»¶

        éè¿ contextmanager æ´é²æä»¶å¥æï¼ç®åç« èèç¹çåå¥é»è¾

        åæ°:
            chapter_dir: å½åç« èç®å½

        è¿å:
            Generator[TextIO]: ä½ä¸ºä¸ä¸æç®¡çå¨ä½¿ç¨çæä»¶å¯¹è±¡
        """
        raw_path = self._raw_stream_path(chapter_dir)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        with raw_path.open("w", encoding="utf-8") as fp:
            yield fp

    # ======== åé¨å·¥å· ========

    def _chapter_dir(self, run_dir: Path, slug: str, order: int) -> Path:
        """æ ¹æ®slug/orderçæç¨³å®ç®å½ï¼ç¡®ä¿åç« åéå­çä¸å¯æåº""
        safe_slug = self._safe_slug(slug)
        folder = f"{order:03d}-{safe_slug}"
        path = run_dir / folder
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _safe_slug(self, slug: str) -> str:
        """ç§»é¤å±é©å­ç¬¦ï¼é¿åçæéæ³æä»¶å¤¹å""
        slug = slug.replace(" ", "-").replace("/", "-")
        return slug or "section"

    def _raw_stream_path(self, chapter_dir: Path) -> Path:
        """è¿åæç« èæµå¼è¾åºå¯¹åºçrawæä»¶è·¯å¾""
        return chapter_dir / "stream.raw"

    def _key(self, run_dir: Path) -> str:
        """å°runç®å½è§£æä¸ºå­å¸ç¼å­çé®ï¼é¿åéå¤è¯»åç£ç""
        return str(run_dir.resolve())

    def _manifest_path(self, run_dir: Path) -> Path:
        """è·åmanifest.jsonçå®éæä»¶è·¯å¾""
        return run_dir / "manifest.json"

    def _write_manifest(self, run_dir: Path, manifest: Dict[str, object]):
        """å°åå­ä¸­çmanifestå¿«ç§å¨éååç£ç""
        self._manifest_path(run_dir).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _read_manifest(self, run_dir: Path) -> Dict[str, object]:
        """
        ä»ç£çè¯»åå·²æmanifest

        è¿ç¨éå¯æå¤å®ä¾åçæ¶å¯åå©å®æ¢å¤ä¸ä¸æ
        """
        manifest_path = self._manifest_path(run_dir)
        if manifest_path.exists():
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        return {"reportId": run_dir.name, "chapters": []}

    def _upsert_record(self, run_dir: Path, record: ChapterRecord):
        """
        æ´æ°æè¿½å manifestä¸­çç« èè®°å½ï¼ä¿è¯é¡ºåºä¸è´

        åé¨ä¼èªå¨æåºå¹¶ååç¼å­+ç£ç
        """
        key = self._key(run_dir)
        manifest = self._manifests.get(key) or self._read_manifest(run_dir)
        chapters: List[Dict[str, object]] = manifest.get("chapters", [])
        chapters = [c for c in chapters if c.get("chapterId") != record.chapter_id]
        chapters.append(record.to_dict())
        chapters.sort(key=lambda x: x.get("order", 0))
        manifest["chapters"] = chapters
        manifest.setdefault("updatedAt", datetime.utcnow().isoformat() + "Z")
        self._manifests[key] = manifest
        self._write_manifest(run_dir, manifest)


__all__ = ["ChapterStorage", "ChapterRecord"]
