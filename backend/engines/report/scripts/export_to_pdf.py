ï»¿#!/usr/bin/env python3
"""
PDFå¯¼åºå·¥å· - ä½¿ç¨Pythonç´æ¥çæPDFï¼æ ä¹±ç 

ç¨æ³:
    python ReportEngine/scripts/export_to_pdf.py <æ¥åIR JSONæä»¶> [è¾åºPDFè·¯å¾]

ç¤ºä¾:
    python ReportEngine/scripts/export_to_pdf.py final_reports/ir/report_ir_xxx.json output.pdf
    python ReportEngine/scripts/export_to_pdf.py final_reports/ir/report_ir_xxx.json
"""

import sys
import json
from pathlib import Path
from loguru import logger

from backend.engines.report.renderers import PDFRenderer


def export_to_pdf(ir_json_path: str, output_pdf_path: str = None):
    """
    ä»IR JSONæä»¶çæPDF

    åæ°:
        ir_json_path: Document IR JSONæä»¶è·¯å¾
        output_pdf_path: è¾åºPDFè·¯å¾ï¼å¯éï¼é»è®¤ä¸ºåï¿½?pdfï¿½?
    """
    ir_path = Path(ir_json_path)

    if not ir_path.exists():
        logger.error(f"æä»¶ä¸å­ï¿½? {ir_path}")
        return False

    # è¯»åIRæ°æ®
    logger.info(f"è¯»åæ¥å: {ir_path}")
    with open(ir_path, 'r', encoding='utf-8') as f:
        document_ir = json.load(f)

    # ç¡®å®è¾åºè·¯å¾
    if output_pdf_path is None:
        output_pdf_path = ir_path.parent / f"{ir_path.stem}.pdf"
    else:
        output_pdf_path = Path(output_pdf_path)

    # çæPDF
    logger.info(f"å¼å§çæPDF...")
    renderer = PDFRenderer()

    try:
        renderer.render_to_pdf(document_ir, output_pdf_path)
        logger.success(f"ï¿½?PDFå·²çï¿½? {output_pdf_path}")
        return True
    except Exception as e:
        logger.error(f"ï¿½?PDFçæå¤±è´¥: {e}")
        logger.exception("è¯¦ç»éè¯¯ä¿¡æ¯:")
        return False


def main():
    """ä¸»å½ï¿½?""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    ir_json_path = sys.argv[1]
    output_pdf_path = sys.argv[2] if len(sys.argv) > 2 else None

    # æ£æ¥ç¯å¢åï¿½?
    import os
    if 'DYLD_LIBRARY_PATH' not in os.environ:
        logger.warning("æªè®¾ç½®DYLD_LIBRARY_PATHï¼å°è¯èªå¨è®¾ï¿½?..")
        os.environ['DYLD_LIBRARY_PATH'] = '/opt/homebrew/lib'

    success = export_to_pdf(ir_json_path, output_pdf_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
