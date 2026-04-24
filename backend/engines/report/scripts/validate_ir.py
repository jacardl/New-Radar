ï»¿#!/usr/bin/env python3
"""
IR ææ¡£éªè¯å·¥å·ï¿½?

å½ä»¤è¡å·¥å·ï¼ç¨äºï¿½?
- æ«ææå® JSON æä»¶ä¸­çææå¾è¡¨åè¡¨æ ¼
- æ¥åç»æé®é¢åæ°æ®ç¼ºï¿½?
- æ¯æèªå¨ä¿®å¤å¸¸è§é®é¢
- æ¯ææ¹éå¤ç

ä½¿ç¨æ¹æ³:
    python -m ReportEngine.scripts.validate_ir chapter-030-section-3-0.json
    python -m ReportEngine.scripts.validate_ir *.json --fix
    python -m ReportEngine.scripts.validate_ir ./output/ --recursive --fix --verbose
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# æ·»å é¡¹ç®æ ¹ç®å½å°è·¯å¾
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from loguru import logger

from backend.engines.report.utils.chart_validator import (
    ChartValidator,
    ChartRepairer,
    ValidationResult,
)
from backend.engines.report.utils.table_validator import (
    TableValidator,
    TableRepairer,
    TableValidationResult,
)


@dataclass
class BlockIssue:
    """åä¸ª block çé®ï¿½?""
    block_type: str
    block_id: str
    path: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    is_fixable: bool = False


@dataclass
class DocumentReport:
    """ææ¡£éªè¯æ¥å"""
    file_path: str
    total_blocks: int = 0
    chart_count: int = 0
    table_count: int = 0
    wordcloud_count: int = 0
    issues: List[BlockIssue] = field(default_factory=list)
    fixed_count: int = 0

    @property
    def has_issues(self) -> bool:
        return len(self.issues) > 0

    @property
    def error_count(self) -> int:
        return sum(len(issue.errors) for issue in self.issues)

    @property
    def warning_count(self) -> int:
        return sum(len(issue.warnings) for issue in self.issues)


class IRValidator:
    """IR ææ¡£éªè¯ï¿½?""

    def __init__(
        self,
        chart_validator: Optional[ChartValidator] = None,
        table_validator: Optional[TableValidator] = None,
        chart_repairer: Optional[ChartRepairer] = None,
        table_repairer: Optional[TableRepairer] = None,
    ):
        self.chart_validator = chart_validator or ChartValidator()
        self.table_validator = table_validator or TableValidator()
        self.chart_repairer = chart_repairer or ChartRepairer(self.chart_validator)
        self.table_repairer = table_repairer or TableRepairer(self.table_validator)

    def validate_document(
        self,
        document: Dict[str, Any],
        file_path: str = "<unknown>",
    ) -> DocumentReport:
        """
        éªè¯æ´ä¸ªææ¡£ï¿½?

        Args:
            document: IR ææ¡£æ°æ®
            file_path: æä»¶è·¯å¾ï¼ç¨äºæ¥åï¼

        Returns:
            DocumentReport: éªè¯æ¥å
        """
        report = DocumentReport(file_path=file_path)

        # éåææç« ï¿½?
        chapters = document.get("chapters", [])
        for chapter_idx, chapter in enumerate(chapters):
            if not isinstance(chapter, dict):
                continue

            chapter_id = chapter.get("chapterId", f"chapter-{chapter_idx}")
            blocks = chapter.get("blocks", [])

            self._validate_blocks(
                blocks,
                f"chapters[{chapter_idx}].blocks",
                chapter_id,
                report,
            )

        return report

    def _validate_blocks(
        self,
        blocks: List[Any],
        path: str,
        chapter_id: str,
        report: DocumentReport,
    ):
        """éå½éªè¯ blocks åè¡¨"""
        if not isinstance(blocks, list):
            return

        for idx, block in enumerate(blocks):
            if not isinstance(block, dict):
                continue

            report.total_blocks += 1
            block_path = f"{path}[{idx}]"
            block_type = block.get("type", "")
            block_id = block.get("widgetId") or block.get("id") or f"block-{idx}"

            # æ ¹æ®ç±»åéªè¯
            if block_type == "widget":
                widget_type = (block.get("widgetType") or "").lower()
                if "chart.js" in widget_type:
                    report.chart_count += 1
                    self._validate_chart(block, block_path, block_id, report)
                elif "wordcloud" in widget_type:
                    report.wordcloud_count += 1
                    self._validate_wordcloud(block, block_path, block_id, report)

            elif block_type == "table":
                report.table_count += 1
                self._validate_table(block, block_path, block_id, report)

            # éå½å¤çåµå¥ blocks
            nested_blocks = block.get("blocks")
            if isinstance(nested_blocks, list):
                self._validate_blocks(nested_blocks, f"{block_path}.blocks", chapter_id, report)

            # å¤ç table rows ä¸­ç blocks
            if block_type == "table":
                rows = block.get("rows", [])
                for row_idx, row in enumerate(rows):
                    if isinstance(row, dict):
                        cells = row.get("cells", [])
                        for cell_idx, cell in enumerate(cells):
                            if isinstance(cell, dict):
                                cell_blocks = cell.get("blocks", [])
                                self._validate_blocks(
                                    cell_blocks,
                                    f"{block_path}.rows[{row_idx}].cells[{cell_idx}].blocks",
                                    chapter_id,
                                    report,
                                )

            # å¤ç list items ä¸­ç blocks
            if block_type == "list":
                items = block.get("items", [])
                for item_idx, item in enumerate(items):
                    if isinstance(item, list):
                        self._validate_blocks(
                            item,
                            f"{block_path}.items[{item_idx}]",
                            chapter_id,
                            report,
                        )

    def _validate_chart(
        self,
        block: Dict[str, Any],
        path: str,
        block_id: str,
        report: DocumentReport,
    ):
        """éªè¯å¾è¡¨"""
        result = self.chart_validator.validate(block)

        if not result.is_valid or result.warnings:
            issue = BlockIssue(
                block_type="chart",
                block_id=block_id,
                path=path,
                errors=result.errors,
                warnings=result.warnings,
                is_fixable=result.has_critical_errors(),
            )
            report.issues.append(issue)

    def _validate_table(
        self,
        block: Dict[str, Any],
        path: str,
        block_id: str,
        report: DocumentReport,
    ):
        """éªè¯è¡¨æ ¼"""
        result = self.table_validator.validate(block)

        if not result.is_valid or result.warnings or result.nested_cells_detected:
            issue = BlockIssue(
                block_type="table",
                block_id=block_id,
                path=path,
                errors=result.errors,
                warnings=result.warnings,
                is_fixable=result.nested_cells_detected or result.has_critical_errors(),
            )

            # æ·»å åµå¥ cells è­¦å
            if result.nested_cells_detected:
                issue.warnings.insert(0, "æ£æµå°åµå¥ cells ç»æï¼LLM å¸¸è§éè¯¯ï¿½?)

            # æ·»å ç©ºååæ ¼ä¿¡æ¯
            if result.empty_cells_count > 0:
                issue.warnings.append(
                    f"ç©ºååæ ¼æ°é: {result.empty_cells_count}/{result.total_cells_count}"
                )

            report.issues.append(issue)

    def _validate_wordcloud(
        self,
        block: Dict[str, Any],
        path: str,
        block_id: str,
        report: DocumentReport,
    ):
        """éªè¯è¯äº"""
        errors: List[str] = []
        warnings: List[str] = []

        # æ£æ¥æ°æ®ç»ï¿½?
        data = block.get("data")
        props = block.get("props", {})

        words_found = False
        words_count = 0

        # æ£æ¥åç§å¯è½çè¯äºæ°æ®è·¯å¾
        data_paths = [
            ("data.words", data.get("words") if isinstance(data, dict) else None),
            ("data.items", data.get("items") if isinstance(data, dict) else None),
            ("data", data if isinstance(data, list) else None),
            ("props.words", props.get("words") if isinstance(props, dict) else None),
            ("props.items", props.get("items") if isinstance(props, dict) else None),
            ("props.data", props.get("data") if isinstance(props, dict) else None),
        ]

        for path_name, value in data_paths:
            if isinstance(value, list) and len(value) > 0:
                words_found = True
                words_count = len(value)

                # éªè¯è¯äºé¡¹æ ¼ï¿½?
                for idx, item in enumerate(value[:5]):  # åªæ£æ¥å5ï¿½?
                    if isinstance(item, dict):
                        word = item.get("word") or item.get("text") or item.get("label")
                        weight = item.get("weight") or item.get("value")
                        if not word:
                            warnings.append(f"{path_name}[{idx}] ç¼ºå° word/text/label å­æ®µ")
                        if weight is None:
                            warnings.append(f"{path_name}[{idx}] ç¼ºå° weight/value å­æ®µ")
                    elif not isinstance(item, (str, list, tuple)):
                        warnings.append(f"{path_name}[{idx}] æ ¼å¼ä¸æ­£ï¿½?)

                break

        if not words_found:
            errors.append("è¯äºæ°æ®ç¼ºå¤±ï¼æªï¿½?data.words, data.items, props.words ç­è·¯å¾æ¾å°æææ°ï¿½?)
        elif words_count == 0:
            warnings.append("è¯äºæ°æ®ä¸ºç©º")

        if errors or warnings:
            issue = BlockIssue(
                block_type="wordcloud",
                block_id=block_id,
                path=path,
                errors=errors,
                warnings=warnings,
                is_fixable=False,  # è¯äºæ°æ®ç¼ºå¤±éå¸¸æ æ³èªå¨ä¿®å¤
            )
            report.issues.append(issue)

    def repair_document(
        self,
        document: Dict[str, Any],
        report: DocumentReport,
    ) -> Tuple[Dict[str, Any], int]:
        """
        ä¿®å¤ææ¡£ä¸­çé®é¢ï¿½?

        Args:
            document: IR ææ¡£æ°æ®
            report: éªè¯æ¥å

        Returns:
            Tuple[Dict[str, Any], int]: (ä¿®å¤åçææ¡£, ä¿®å¤æ°é)
        """
        fixed_count = 0

        # éåææç« ï¿½?
        chapters = document.get("chapters", [])
        for chapter in chapters:
            if not isinstance(chapter, dict):
                continue

            blocks = chapter.get("blocks", [])
            chapter["blocks"], chapter_fixed = self._repair_blocks(blocks)
            fixed_count += chapter_fixed

        return document, fixed_count

    def _repair_blocks(
        self,
        blocks: List[Any],
    ) -> Tuple[List[Any], int]:
        """éå½ä¿®å¤ blocks åè¡¨"""
        if not isinstance(blocks, list):
            return blocks, 0

        fixed_count = 0
        repaired_blocks: List[Any] = []

        for block in blocks:
            if not isinstance(block, dict):
                repaired_blocks.append(block)
                continue

            block_type = block.get("type", "")

            # ä¿®å¤è¡¨æ ¼
            if block_type == "table":
                result = self.table_repairer.repair(block)
                if result.has_changes():
                    block = result.repaired_block
                    fixed_count += 1
                    logger.info(f"ä¿®å¤è¡¨æ ¼: {result.changes}")

            # ä¿®å¤å¾è¡¨
            elif block_type == "widget":
                widget_type = (block.get("widgetType") or "").lower()
                if "chart.js" in widget_type:
                    result = self.chart_repairer.repair(block)
                    if result.has_changes():
                        block = result.repaired_block
                        fixed_count += 1
                        logger.info(f"ä¿®å¤å¾è¡¨: {result.changes}")

            # éå½å¤çåµå¥ blocks
            nested_blocks = block.get("blocks")
            if isinstance(nested_blocks, list):
                block["blocks"], nested_fixed = self._repair_blocks(nested_blocks)
                fixed_count += nested_fixed

            # å¤ç table rows ä¸­ç blocks
            if block_type == "table":
                rows = block.get("rows", [])
                for row in rows:
                    if isinstance(row, dict):
                        cells = row.get("cells", [])
                        for cell in cells:
                            if isinstance(cell, dict):
                                cell_blocks = cell.get("blocks", [])
                                cell["blocks"], cell_fixed = self._repair_blocks(cell_blocks)
                                fixed_count += cell_fixed

            # å¤ç list items ä¸­ç blocks
            if block_type == "list":
                items = block.get("items", [])
                for i, item in enumerate(items):
                    if isinstance(item, list):
                        items[i], item_fixed = self._repair_blocks(item)
                        fixed_count += item_fixed

            repaired_blocks.append(block)

        return repaired_blocks, fixed_count


def print_report(report: DocumentReport, verbose: bool = False):
    """æå°éªè¯æ¥å"""
    print(f"\n{'=' * 60}")
    print(f"æä»¶: {report.file_path}")
    print(f"{'=' * 60}")

    print(f"\nð ç»è®¡:")
    print(f"  - ï¿½?blocks: {report.total_blocks}")
    print(f"  - å¾è¡¨æ°é: {report.chart_count}")
    print(f"  - è¡¨æ ¼æ°é: {report.table_count}")
    print(f"  - è¯äºæ°é: {report.wordcloud_count}")

    if report.has_issues:
        print(f"\nâ ï¸  åç° {len(report.issues)} ä¸ªé®ï¿½?")
        print(f"  - éè¯¯: {report.error_count}")
        print(f"  - è­¦å: {report.warning_count}")

        if verbose:
            for issue in report.issues:
                print(f"\n  [{issue.block_type}] {issue.block_id}")
                print(f"    è·¯å¾: {issue.path}")
                if issue.errors:
                    for error in issue.errors:
                        print(f"    ï¿½?{error}")
                if issue.warnings:
                    for warning in issue.warnings:
                        print(f"    â ï¸  {warning}")
                if issue.is_fixable:
                    print(f"    ð§ å¯èªå¨ä¿®ï¿½?)
    else:
        print(f"\nï¿½?æªåç°é®ï¿½?)

    if report.fixed_count > 0:
        print(f"\nð§ å·²ä¿®ï¿½?{report.fixed_count} ä¸ªé®ï¿½?)


def validate_file(
    file_path: Path,
    validator: IRValidator,
    fix: bool = False,
    verbose: bool = False,
) -> DocumentReport:
    """éªè¯åä¸ªæä»¶"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            document = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"JSON è§£æéè¯¯: {file_path}: {e}")
        report = DocumentReport(file_path=str(file_path))
        report.issues.append(BlockIssue(
            block_type="document",
            block_id="root",
            path="",
            errors=[f"JSON è§£æéè¯¯: {e}"],
        ))
        return report
    except Exception as e:
        logger.error(f"è¯»åæä»¶éè¯¯: {file_path}: {e}")
        report = DocumentReport(file_path=str(file_path))
        report.issues.append(BlockIssue(
            block_type="document",
            block_id="root",
            path="",
            errors=[f"è¯»åæä»¶éè¯¯: {e}"],
        ))
        return report

    # éªè¯ææ¡£
    report = validator.validate_document(document, str(file_path))

    # ä¿®å¤é®é¢
    if fix and report.has_issues:
        fixable_issues = [i for i in report.issues if i.is_fixable]
        if fixable_issues:
            logger.info(f"å°è¯ä¿®å¤ {len(fixable_issues)} ä¸ªé®ï¿½?..")
            document, fixed_count = validator.repair_document(document, report)
            report.fixed_count = fixed_count

            if fixed_count > 0:
                # ä¿å­ä¿®å¤åçæä»¶
                backup_path = file_path.with_suffix(f".bak{file_path.suffix}")
                try:
                    # åå»ºå¤ä»½
                    import shutil
                    shutil.copy(file_path, backup_path)
                    logger.info(f"å·²åå»ºå¤ï¿½? {backup_path}")

                    # ä¿å­ä¿®å¤åçæä»¶
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(document, f, ensure_ascii=False, indent=2)
                    logger.info(f"å·²ä¿å­ä¿®å¤åçæï¿½? {file_path}")
                except Exception as e:
                    logger.error(f"ä¿å­æä»¶å¤±è´¥: {e}")

    return report


def main():
    """ä¸»å½ï¿½?""
    parser = argparse.ArgumentParser(
        description="IR ææ¡£éªè¯å·¥å·",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ç¤ºä¾:
  %(prog)s chapter-030-section-3-0.json
  %(prog)s *.json --fix
  %(prog)s ./output/ --recursive --fix --verbose
        """,
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="è¦éªè¯ç JSON æä»¶æç®ï¿½?,
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="éå½å¤çç®å½",
    )
    parser.add_argument(
        "-f", "--fix",
        action="store_true",
        help="èªå¨ä¿®å¤å¸¸è§é®é¢",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="æ¾ç¤ºè¯¦ç»ä¿¡æ¯",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="ç¦ç¨å½©è²è¾åº",
    )

    args = parser.parse_args()

    # éç½®æ¥å¿
    logger.remove()
    if args.verbose:
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.add(sys.stderr, level="INFO")

    # æ¶éæä»¶
    files: List[Path] = []
    for path_str in args.paths:
        path = Path(path_str)
        if path.is_file():
            if path.suffix.lower() == ".json":
                files.append(path)
        elif path.is_dir():
            if args.recursive:
                files.extend(path.rglob("*.json"))
            else:
                files.extend(path.glob("*.json"))
        else:
            # å¯è½ï¿½?glob æ¨¡å¼
            import glob
            matched = glob.glob(path_str)
            for m in matched:
                mp = Path(m)
                if mp.is_file() and mp.suffix.lower() == ".json":
                    files.append(mp)

    if not files:
        print("æªæ¾ï¿½?JSON æä»¶")
        sys.exit(1)

    print(f"æ¾å° {len(files)} ä¸ªæï¿½?)

    # åå»ºéªè¯ï¿½?
    validator = IRValidator()

    # éªè¯æä»¶
    total_issues = 0
    total_fixed = 0
    reports: List[DocumentReport] = []

    for file_path in files:
        report = validate_file(file_path, validator, args.fix, args.verbose)
        reports.append(report)
        total_issues += len(report.issues)
        total_fixed += report.fixed_count

        if args.verbose or report.has_issues:
            print_report(report, args.verbose)

    # æå°æ»ç»
    print(f"\n{'=' * 60}")
    print("æ»ç»")
    print(f"{'=' * 60}")
    print(f"  - æä»¶ï¿½? {len(files)}")
    print(f"  - é®é¢æ»æ°: {total_issues}")
    if args.fix:
        print(f"  - å·²ä¿®ï¿½? {total_fixed}")

    # è¿åéå½çéåºç 
    if total_issues > 0 and total_fixed < total_issues:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
