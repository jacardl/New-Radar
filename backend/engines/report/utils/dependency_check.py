"""
æ£æµç³»ç»ä¾èµå·¥å?
ç¨äºæ£æµ?PDF çææéçç³»ç»ä¾èµ?
"""
import os
import sys
import platform
from pathlib import Path
from loguru import logger
from ctypes import util as ctypes_util

BOX_CONTENT_WIDTH = 62


def _box_line(text: str = "") -> str:
    """Render a single line inside the 66-char help box."""
    return f"â? {text:<{BOX_CONTENT_WIDTH}}â\n"


def _get_platform_specific_instructions():
    """
    è·åéå¯¹å½åå¹³å°çå®è£è¯´æ?

    Returns:
        str: å¹³å°ç¹å®çå®è£è¯´æ?
    """
    system = platform.system()

    def _box_lines(lines):
        """æ¹éå°å¤è¡ææ¬åè£æå¸¦è¾¹æ¡çæç¤ºå?""
        return "".join(_box_line(line) for line in lines)

    if system == "Darwin":  # macOS
        return _box_lines(
            [
                "ð macOS ç³»ç»è§£å³æ¹æ¡ï¼?,
                "",
                "æ­¥éª¤ 1: å®è£ä¾èµï¼å®¿ä¸»æºæ§è¡ï¼?,
                "  brew install pango gdk-pixbuf libffi",
                "",
                "æ­¥éª¤ 2: è®¾ç½® DYLD_LIBRARY_PATHï¼å¿åï¼",
                "  Apple Silicon:",
                " export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH",
                "  Intel:",
                " export DYLD_LIBRARY_PATH=/usr/local/lib:$DYLD_LIBRARY_PATH",
                "",
                "æ­¥éª¤ 3: æ°¸ä¹çæï¼æ¨èï¼",
                "  å°?export DYLD_LIBRARY_PATH=... è¿½å å?~/.zshrc",
                "  Apple ç?/opt/homebrew/libï¼Intel ç?/usr/local/lib",
                "  æ§è¡ source ~/.zshrc ååæå¼æ°ç»ç«?,
                "",
                "æ­¥éª¤ 4: æ°å¼ç»ç«¯æ§è¡éªè¯",
                "  python -m ReportEngine.utils.dependency_check",
                "  è¾åºå?"â Pango ä¾èµæ£æµéè¿â?å³éç½®æ­£ç¡?,
            ]
        )
    elif system == "Linux":
        return _box_lines(
            [
                "ð§ Linux ç³»ç»è§£å³æ¹æ¡ï¼?,
                "",
                "Ubuntu/Debianï¼å®¿ä¸»æºæ§è¡ï¼ï¼",
                "  sudo apt-get update",
                "  sudo apt-get install -y \\",
                "    libpango-1.0-0 libpangoft2-1.0-0 libffi-dev libcairo2",
                "    libgdk-pixbuf-2.0-0ï¼ç¼ºå¤±æ¶æ¹ä¸º libgdk-pixbuf2.0-0ï¼?,
                "",
                "CentOS/RHELï¼?,
                "  sudo yum install -y pango gdk-pixbuf2 libffi-devel cairo",
                "",
                "Docker é¨ç½²æ éé¢å¤å®è£ï¼éåå·²åå«ä¾èµ",
            ]
        )
    elif system == "Windows":
        return _box_lines(
            [
                "ðª Windows ç³»ç»è§£å³æ¹æ¡ï¼?,
                "",
                "æ­¥éª¤ 1: å®è£ GTK3 Runtimeï¼å®¿ä¸»æºæ§è¡ï¼?,
                "  ä¸è½½é¡? README ä¸­ç GTK3 Runtime é¾æ¥ï¼å»ºè®®é»è®¤è·¯å¾ï¼",
                "",
                "æ­¥éª¤ 2: å°?GTK å®è£ç®å½ä¸ç bin å å¥ PATHï¼éæ°ç»ç«¯ï¼",
                "  set PATH=C:\\Program Files\\GTK3-Runtime Win64\\bin;%PATH%",
                "  èªå®ä¹è·¯å¾è¯·æ¿æ¢ï¼æè®¾ç½®ç¯å¢åé GTK_BIN_PATH",
                "  å¯é? æ°¸ä¹æ·»å  PATH ç¤ºä¾:",
                "    setx PATH \"C:\\Program Files\\GTK3-Runtime Win64\\bin;%PATH%\"",
                "",
                "æ­¥éª¤ 3: éªè¯ï¼æ°ç»ç«¯æ§è¡ï¼?,
                "  python -m ReportEngine.utils.dependency_check",
                "  è¾åºå?"â Pango ä¾èµæ£æµéè¿â?å³éç½®æ­£ç¡?,
            ]
        )
    else:
        return _box_lines(["è¯·æ¥ç?PDF å¯¼åº README äºè§£æ¨ç³»ç»çå®è£æ¹æ³"])


def _ensure_windows_gtk_paths():
    """
    ä¸?Windows èªå¨è¡¥å GTK/Pango è¿è¡æ¶æç´¢è·¯å¾ï¼è§£å³ DLL æªæ¾å°é®é¢

    Returns:
        str | None: æåæ·»å çè·¯å¾ï¼æ²¡æå½ä¸­åä¸º Noneï¼?
    """
    if platform.system() != "Windows":
        return None

    candidates = []
    seen = set()

    def _add_candidate(path_like):
        """æ¶éå¯è½çGTKå®è£è·¯å¾ï¼é¿åéå¤å¹¶å¼å®¹ç¨æ·èªå®ä¹ç®å½?""
        if not path_like:
            return
        p = Path(path_like)
        # å¦æä¼ å¥çæ¯å®è£æ ¹ç®å½ï¼å°è¯æ¼æ¥ bin
        if p.is_dir() and p.name.lower() == "bin":
            key = str(p.resolve()).lower()
            if key not in seen:
                seen.add(key)
                candidates.append(p)
        else:
            for maybe in (p, p / "bin"):
                key = str(maybe.resolve()).lower()
                if maybe.exists() and key not in seen:
                    seen.add(key)
                    candidates.append(maybe)

    # ç¨æ·èªå®ä¹æç¤ºä¼å?
    for env_var in ("GTK3_RUNTIME_PATH", "GTK_RUNTIME_PATH", "GTK_BIN_PATH", "GTK_BIN_DIR", "GTK_PATH"):
        _add_candidate(os.environ.get(env_var))

    program_files = os.environ.get("ProgramFiles", r"C:\\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\\Program Files (x86)")
    default_dirs = [
        Path(program_files) / "GTK3-Runtime Win64",
        Path(program_files_x86) / "GTK3-Runtime Win64",
        Path(program_files) / "GTK3-Runtime Win32",
        Path(program_files_x86) / "GTK3-Runtime Win32",
        Path(program_files) / "GTK3-Runtime",
        Path(program_files_x86) / "GTK3-Runtime",
    ]

    # å¸¸è§èªå®ä¹å®è£ä½ç½®ï¼å¶ä»çç¬¦ / DevelopSoftware ç®å½ï¼?
    common_drives = ["C", "D", "E", "F"]
    common_names = ["GTK3-Runtime Win64", "GTK3-Runtime Win32", "GTK3-Runtime"]
    for drive in common_drives:
        root = Path(f"{drive}:/")
        # æ£æµè·¯å¾æ¯å¦å­å¨å¹¶å¯è®¿é?
        try:
            if root.exists():
                for name in common_names:
                    default_dirs.append(root / name)
                    default_dirs.append(root / "DevelopSoftware" / name)
        except OSError as e:
            # print(f'ç{drive}ä¸å­å¨æè¢«å å¯ï¼å·²è·³è¿?)
            pass

    # æ«æ Program Files ä¸ææä»¥ GTK å¼å¤´çç®å½ï¼ééèªå®ä¹å®è£ç®å½å
    for root in (program_files, program_files_x86):
        root_path = Path(root)
        if root_path.exists():
            for child in root_path.glob("GTK*"):
                default_dirs.append(child)

    for d in default_dirs:
        _add_candidate(d)

    # å¦æç¨æ·å·²æèªå®ä¹è·¯å¾å å?PATHï¼ä¹å°è¯è¯å«
    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    for entry in path_entries:
        if not entry:
            continue
        # ç²ç­åå« gtk æ?pango çç®å½?
        if "gtk" in entry.lower() or "pango" in entry.lower():
            _add_candidate(entry)

    for path in candidates:
        if not path or not path.exists():
            continue
        if not any(path.glob("pango*-1.0-*.dll")) and not (path / "pango-1.0-0.dll").exists():
            continue

        try:
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(str(path))
        except Exception:
            # å¦ææ·»å å¤±è´¥ï¼ç»§ç»­å°è¯?PATH æ¹å¼
            pass

        current_path = os.environ.get("PATH", "")
        if str(path) not in current_path.split(";"):
            os.environ["PATH"] = f"{path};{current_path}"

        return str(path)

    return None


def prepare_pango_environment():
    """
    åå§åè¿è¡æéçæ¬å°ä¾èµæç´¢è·¯å¾ï¼å½åä¸»è¦éå¯¹ Windows å?macOSï¼

    Returns:
        str | None: æåæ·»å çè·¯å¾ï¼æ²¡æå½ä¸­åä¸º Noneï¼?
    """
    system = platform.system()
    if system == "Windows":
        return _ensure_windows_gtk_paths()
    if system == "Darwin":
        # èªå¨è¡¥å¨ DYLD_LIBRARY_PATHï¼å¼å®?Apple Silicon ä¸?Intel
        candidates = [Path("/opt/homebrew/lib"), Path("/usr/local/lib")]
        current = os.environ.get("DYLD_LIBRARY_PATH", "")
        added = []
        for c in candidates:
            if c.exists() and str(c) not in current.split(":"):
                added.append(str(c))
        if added:
            os.environ["DYLD_LIBRARY_PATH"] = ":".join(added + ([current] if current else []))
            return os.environ["DYLD_LIBRARY_PATH"]
    return None


def _probe_native_libs():
    """
    ä½¿ç¨ ctypes æ¥æ¾å³é®åçåºï¼å¸®å©å®ä½ç¼ºå¤±ç»ä»¶

    Returns:
        list[str]: æªæ¾å°çåºæ è¯?
    """
    system = platform.system()
    targets = []

    if system == "Windows":
        targets = [
            ("pango", ["pango-1.0-0"]),
            ("gobject", ["gobject-2.0-0"]),
            ("gdk-pixbuf", ["gdk_pixbuf-2.0-0"]),
            ("cairo", ["cairo-2"]),
        ]
    else:
        targets = [
            ("pango", ["pango-1.0"]),
            ("gobject", ["gobject-2.0"]),
            ("gdk-pixbuf", ["gdk_pixbuf-2.0"]),
            ("cairo", ["cairo", "cairo-2"]),
        ]

    missing = []
    for key, variants in targets:
        found = any(ctypes_util.find_library(v) for v in variants)
        if not found:
            missing.append(key)
    return missing


def check_pango_available():
    """
    æ£æµ?Pango åºæ¯å¦å¯ç?

    Returns:
        tuple: (is_available: bool, message: str)
    """
    added_path = prepare_pango_environment()
    missing_native = _probe_native_libs()

    try:
        # å°è¯å¯¼å¥ weasyprint å¹¶åå§å Pango
        from weasyprint import HTML
        from weasyprint.text.ffi import ffi, pango

        # å°è¯è°ç¨ Pango å½æ°æ¥ç¡®è®¤åºå¯ç¨
        pango.pango_version()

        return True, "â?Pango ä¾èµæ£æµéè¿ï¼PDF å¯¼åºåè½å¯ç¨"
    except OSError as e:
        # Pango åºæªå®è£ææ æ³å è½?
        error_msg = str(e)
        platform_instructions = _get_platform_specific_instructions()
        windows_hint = ""
        if platform.system() == "Windows":
            prefix = "å·²å°è¯èªå¨æ·»å?GTK è·¯å¾: "
            max_path_len = BOX_CONTENT_WIDTH - len(prefix)
            path_display = added_path or "æªæ¾å°é»è®¤è·¯å¾?
            if len(path_display) > max_path_len:
                path_display = path_display[: max_path_len - 3] + "..."
            windows_hint = _box_line(prefix + path_display)
            arch_note = _box_line("ð è¥å·²å®è£ä»æ¥éï¼ç¡®è®¤ Python ä¸?GTK ä½æ°ä¸è´åéå¼ç»ç«¯")
        else:
            arch_note = ""

        missing_note = ""
        if missing_native:
            missing_str = ", ".join(missing_native)
            missing_note = _box_line(f"æªè¯å«å°çä¾èµ? {missing_str}")

        if 'gobject' in error_msg.lower() or 'pango' in error_msg.lower() or 'gdk' in error_msg.lower():
            box_top = "â? + "â? * 64 + "â\n"
            box_bottom = "â? + "â? * 64 + "â?
            return False, (
                box_top
                + _box_line("â ï¸  PDF å¯¼åºä¾èµç¼ºå¤±")
                + _box_line()
                + _box_line("ð PDF å¯¼åºåè½å°ä¸å¯ç¨ï¼å¶ä»åè½ä¸åå½±åï¼")
                + _box_line()
                + windows_hint
                + arch_note
                + missing_note
                + platform_instructions
                + _box_line()
                + _box_line("ð ææ¡£ï¼static/Partial README for PDF Exporting/README.md")
                + box_bottom
            )
        return False, f"â?PDF ä¾èµå è½½å¤±è´¥: {error_msg}ï¼ç¼ºå¤?æªè¯å? {', '.join(missing_native) if missing_native else 'æªç¥'}"
    except ImportError as e:
        # weasyprint æªå®è£?
        return False, (
            "â?WeasyPrint æªå®è£\n"
            "è§£å³æ¹æ³: pip install weasyprint"
        )
    except Exception as e:
        # å¶ä»æªç¥éè¯¯
        return False, f"â?PDF ä¾èµæ£æµå¤±è´? {e}"


def log_dependency_status():
    """
    è®°å½ç³»ç»ä¾èµç¶æå°æ¥å¿
    """
    is_available, message = check_pango_available()

    if is_available:
        logger.success(message)
    else:
        logger.warning(message)
        logger.info("ð¡ æç¤ºï¼PDF å¯¼åºåè½éè¦?Pango åºæ¯æï¼ä½ä¸å½±åç³»ç»å¶ä»åè½çæ­£å¸¸ä½¿ç?)
        logger.info("ð å®è£è¯´æè¯·åèï¼static/Partial README for PDF Exporting/README.md")

    return is_available


if __name__ == "__main__":
    # ç¨äºç¬ç«æµè¯
    is_available, message = check_pango_available()
    print(message)
    sys.exit(0 if is_available else 1)
