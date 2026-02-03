import os
import base64
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from app.core.database import get_job
from app.core.paths import get_output_dir, _is_vercel
from app.utils.utils import write_text_to_file
from app.core.file_versions import file_version_manager


ExportResult = Dict[str, Any]


def _normalize_format(fmt: Optional[str]) -> Optional[str]:
    if not fmt:
        return None
    fmt = fmt.lower()
    if fmt in {"pdf", "docx", "txt"}:
        return fmt
    # Gracefully map common aliases
    if fmt in {"text", "plain"}:
        return "txt"
    return None


def _infer_input_format(job_result: Dict[str, Any]) -> str:
    # 1) Explicit field if present
    explicit = _normalize_format(job_result.get("input_format"))
    if explicit:
        return explicit

    # 2) Infer from original_file_path extension
    original_path = job_result.get("original_file_path") or ""
    ext = os.path.splitext(str(original_path))[1].lower()
    if ext == ".pdf":
        return "pdf"
    if ext in {".docx", ".doc"}:
        # Normalize legacy .doc to docx container
        return "docx"
    return "txt"


def _resolve_effective_format(job_result: Dict[str, Any], export_format: Optional[str]) -> Tuple[str, List[str]]:
    warnings: List[str] = []
    input_fmt = _infer_input_format(job_result)

    if not export_format or export_format in ("same", "original"):
        return input_fmt, warnings

    fmt = _normalize_format(export_format)
    if not fmt:
        # Invalid override – fall back to input format and warn
        warnings.append(f"invalid_export_format_{export_format}")
        return input_fmt, warnings

    return fmt, warnings


def _get_final_text_and_path(job_result: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], List[str]]:
    """
    Try to get refined_text and output_path for the final pass.
    Prefer explicit fields; fall back to file_version_manager if needed.
    """
    warnings: List[str] = []
    refined_text = job_result.get("refined_text")
    output_path = job_result.get("output_path")

    if refined_text and output_path:
        return refined_text, output_path, warnings

    # Fallback: try to reconstruct from file_version_manager
    file_id = job_result.get("file_id")
    final_pass = job_result.get("final_pass")
    if file_id and isinstance(final_pass, int):
        try:
            version = file_version_manager.get_version(file_id=file_id, pass_number=final_pass)
        except TypeError:
            # Older signature without keywords
            version = file_version_manager.get_version(file_id, final_pass)
        if version:
            if not refined_text:
                refined_text = version.content
            if not output_path:
                output_path = version.file_path

    if not refined_text:
        warnings.append("missing_refined_text")
    if not output_path:
        warnings.append("missing_output_path")

    return refined_text, output_path, warnings


def _get_version_text_and_path(file_id: str, pass_number: int) -> Tuple[Optional[str], Optional[str], List[str]]:
    """
    Load a specific pass version from file_version_manager.
    """
    warnings: List[str] = []
    refined_text: Optional[str] = None
    output_path: Optional[str] = None

    try:
        try:
            version = file_version_manager.get_version(file_id=file_id, pass_number=pass_number)
        except TypeError:
            version = file_version_manager.get_version(file_id, pass_number)
    except Exception as e:
        warnings.append(f"version_load_error:{type(e).__name__}")
        version = None

    if version:
        refined_text = getattr(version, "content", None)
        output_path = getattr(version, "file_path", None)
    else:
        warnings.append("version_not_found")

    if not refined_text:
        warnings.append("missing_refined_text")
    if not output_path:
        warnings.append("missing_output_path")

    return refined_text, output_path, warnings


def _infer_format_from_path(path: Optional[str]) -> str:
    if not path:
        return "txt"
    ext = os.path.splitext(str(path))[1].lower()
    if ext == ".pdf":
        return "pdf"
    if ext in {".docx", ".doc"}:
        return "docx"
    return "txt"


def export_refined_document(
    job_id: str,
    export_format: Optional[str] = None,
    file_id: Optional[str] = None,
    pass_number: Optional[int] = None,
) -> ExportResult:
    """
    Format-aware export for a refinement job's final pass.

    Returns a structured payload:
    {
      "status": "success | partial_success | error",
      "format": "pdf | docx | txt | null",
      "download_url": "...",
      "warnings": [...]
    }
    """
    warnings: List[str] = []

    job_result: Dict[str, Any] = {}
    refined_text: Optional[str] = None
    existing_path: Optional[str] = None

    # Branch 1: explicit file_id + pass_number (per-pass export)
    if file_id and isinstance(pass_number, int):
        refined_text, existing_path, text_path_warnings = _get_version_text_and_path(file_id, pass_number)
        warnings.extend(text_path_warnings)
        if not refined_text:
            return {
                "status": "error",
                "format": None,
                "download_url": None,
                "warnings": warnings + ["no_refined_text_available"],
            }
        # Derive input format directly from the stored path for this pass
        job_result = {
            "input_format": _infer_format_from_path(existing_path),
            "original_file_path": existing_path,
            "final_pass": pass_number,
            "file_id": file_id,
        }
    else:
        # Branch 2: final-pass export using job.result contract
        job = get_job(job_id)
        if not job or not getattr(job, "result", None):
            return {
                "status": "error",
                "format": None,
                "download_url": None,
                "warnings": ["job_not_found_or_no_result"],
            }
        job_result = job.result or {}
        refined_text, existing_path, text_path_warnings = _get_final_text_and_path(job_result)
        warnings.extend(text_path_warnings)
        if not refined_text:
            return {
                "status": "error",
                "format": None,
                "download_url": None,
                "warnings": warnings + ["no_refined_text_available"],
            }

    effective_format, format_warnings = _resolve_effective_format(job_result, export_format)
    warnings.extend(format_warnings)

    # Determine base name and extension
    original_path = job_result.get("original_file_path") or existing_path or f"job_{job_id}"
    base_name = os.path.splitext(os.path.basename(str(original_path)))[0] or f"job_{job_id}"

    if effective_format == "pdf":
        ext = ".pdf"
    elif effective_format == "docx":
        ext = ".docx"
    else:
        ext = ".txt"

    output_dir = str(get_output_dir())
    os.makedirs(output_dir, exist_ok=True)

    final_path = None
    try:
        # Prefer reusing existing_path iff it matches desired extension
        if existing_path and os.path.exists(existing_path):
            existing_ext = os.path.splitext(existing_path)[1].lower()
            desired_ext = ext.lower()
            if existing_ext == desired_ext:
                final_path = existing_path

        if not final_path:
            # Render a new file in the desired format, using original_file_path as style skeleton when possible
            original_file_path = job_result.get("original_file_path") or existing_path
            final_path = write_text_to_file(
                text=refined_text,
                output_dir=output_dir,
                base_name=base_name,
                ext=ext,
                original_file=original_file_path,
                iteration=job_result.get("final_pass"),
            )
    except Exception as e:
        # Rendering failure must not crash the API; surface as error
        warnings.append(f"render_error:{type(e).__name__}")
        return {
            "status": "error",
            "format": effective_format,
            "download_url": None,
            "warnings": warnings,
        }

    if not final_path or not os.path.exists(final_path):
        return {
            "status": "error",
            "format": effective_format,
            "download_url": None,
            "warnings": warnings + ["output_file_missing"],
        }

    # CRITICAL FIX: Ensure file is in output directory for serving
    # If file is in a temp location, copy it to output directory
    output_dir_path = get_output_dir()
    final_path_obj = Path(final_path)
    
    if not str(final_path_obj.parent).startswith(str(output_dir_path)):
        # File is NOT in output directory - copy it there
        import shutil
        new_filename = f"{base_name}{ext}"
        new_path = output_dir_path / new_filename
        try:
            shutil.copy2(final_path, new_path)
            final_path = str(new_path)
        except Exception as e:
            warnings.append(f"failed_to_copy_to_output:{type(e).__name__}")
    
    filename = os.path.basename(final_path)
    
    # DEBUG: Log file path info
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Export final_path: {final_path}")
    logger.info(f"Export filename: {filename}")
    logger.info(f"File exists: {os.path.exists(final_path)}")
    logger.info(f"Is Vercel: {_is_vercel()}")
    
    # HYBRID APPROACH: Handle both Vercel (serverless) and traditional deployments
    result = {
        "status": "success" if not warnings else "partial_success",
        "format": effective_format,
        "warnings": warnings,
    }
    
    # On Vercel/serverless: Include file content directly (base64) since /tmp is ephemeral
    # On traditional: Use file path since process persists
    if _is_vercel():
        try:
            # Read file content and encode as base64
            with open(final_path, 'rb') as f:
                file_content = f.read()
            result["file_content"] = base64.b64encode(file_content).decode('utf-8')
            result["filename"] = filename
            result["download_url"] = None  # No URL on serverless, use content instead
            warnings.append("serverless_mode_file_content_included")
        except Exception as e:
            # Fallback: try to serve via URL anyway (may fail)
            result["download_url"] = f"/files/serve?filename={filename}"
            warnings.append(f"failed_to_encode_file:{type(e).__name__}")
    else:
        # Traditional deployment: Use file serving endpoint
        result["download_url"] = f"/files/serve?filename={filename}"
    
    result["warnings"] = warnings
    return result

