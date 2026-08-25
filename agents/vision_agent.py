"""
ULTRON V3 - Vision Agent
Phase 2B.5 Domain Agent for Screen Capture, Camera Processing, Image Analysis, and OCR.
Integrates BaseUltronAgent, WorkspaceACL, ArtifactRegistry, and AgentMemoryBus.
"""

import os
import sys
import time
import uuid
from typing import Dict, Any, Optional, List

from agents.base_ultron_agent import BaseUltronAgent
from core.logger import logger

# Lazy / Safe imports for vision libraries
try:
    from PIL import Image, ImageGrab
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

import shutil

try:
    import pytesseract
    # Dynamic discovery for Tesseract binary path
    tesseract_env = os.getenv("TESSERACT_PATH")
    if tesseract_env and os.path.exists(tesseract_env):
        pytesseract.pytesseract.tesseract_cmd = tesseract_env
    else:
        system_tesseract = shutil.which("tesseract")
        if system_tesseract:
            pytesseract.pytesseract.tesseract_cmd = system_tesseract
        else:
            common_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                "/usr/bin/tesseract",
                "/usr/local/bin/tesseract",
            ]
            for p in common_paths:
                if os.path.exists(p):
                    pytesseract.pytesseract.tesseract_cmd = p
                    break
    HAS_PYTESSERACT = True
except ImportError:
    HAS_PYTESSERACT = False


class VisionAgent(BaseUltronAgent):
    """
    Vision & Optical Processing Domain Agent.
    
    Capabilities:
    - capture_screen: Desktop screenshot capture
    - capture_camera: Webcam frame capture with dynamic camera enumeration
    - analyze_image: Image inspection & visual question answering
    - analyze_screen: Full screen capture + visual analysis
    - ocr: Text extraction from image or active screen
    - describe_image: Visual scene description
    """

    def __init__(
        self,
        agent_id: str = "vision_agent",
        name: str = "Vision Agent",
        description: str = "Handles screen capture, camera access, optical character recognition (OCR), and image analysis.",
        bus: Optional[Any] = None,
        version: str = "1.0.0",
    ) -> None:
        capabilities = [
            "capture_screen",
            "capture_camera",
            "analyze_image",
            "analyze_screen",
            "ocr",
            "describe_image",
        ]
        supported_skills = ["screen_capture", "camera_capture", "ocr_extraction", "image_analysis"]
        super().__init__(
            agent_id=agent_id,
            name=name,
            description=description,
            capabilities=capabilities,
            supported_skills=supported_skills,
            bus=bus,
            version=version,
        )

    def _do_execute_task(self, task_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardized task execution entry point for VisionAgent.
        Supported actions: capture_screen, capture_camera, analyze_image, analyze_screen, ocr, describe_image.
        """
        action = payload.get("action", "").lower().strip()
        t_start = time.perf_counter()

        logger.info(f"[VisionAgent] Executing action '{action}'...")

        try:
            if action in ["capture_screen", "screenshot"]:
                res = self._capture_screen(payload)
            elif action in ["capture_camera", "camera_frame", "webcam"]:
                res = self._capture_camera(payload)
            elif action in ["ocr", "read_screen", "extract_text"]:
                res = self._run_ocr(payload)
            elif action in ["analyze_image", "analyze_screen", "describe_image", "image_analysis"]:
                res = self._analyze_image(payload)
            else:
                res = {
                    "status": "ERROR",
                    "available": False,
                    "reason": f"Unknown or unsupported vision action '{action}'.",
                }

            latency_ms = (time.perf_counter() - t_start) * 1000.0
            if isinstance(res, dict):
                res["latency_ms"] = round(latency_ms, 2)
            return res

        except Exception as err:
            logger.error(f"[VisionAgent] Error executing action '{action}': {err}")
            return {
                "status": "ERROR",
                "available": False,
                "reason": str(err),
                "latency_ms": round((time.perf_counter() - t_start) * 1000.0, 2),
            }

    def _capture_screen(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Capture desktop screenshot safely across platforms."""
        if not HAS_PIL:
            return {
                "status": "ERROR",
                "available": False,
                "reason": "Pillow (PIL) library is not installed in environment.",
            }

        output_dir = payload.get("output_dir", "data/screenshots")
        os.makedirs(output_dir, exist_ok=True)
        filename = payload.get("filename") or f"screenshot_{uuid.uuid4().hex[:8]}.png"
        filepath = os.path.join(output_dir, filename)

        try:
            image = ImageGrab.grab()
            image.save(filepath, "PNG")
            width, height = image.size

            logger.info(f"[VisionAgent] Screenshot captured ({width}x{height}) -> {filepath}")
            return {
                "status": "SUCCESS",
                "available": True,
                "filepath": filepath,
                "resolution": f"{width}x{height}",
                "result": f"Screenshot captured successfully: {filepath} ({width}x{height})",
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "available": False,
                "reason": f"Screen capture failed: {e}",
            }

    def _capture_camera(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Capture single frame from available webcam dynamically with proper handle cleanup."""
        if not HAS_CV2:
            return {
                "status": "ERROR",
                "available": False,
                "reason": "OpenCV (cv2) library is not installed in environment.",
            }

        camera_index = payload.get("camera_index", 0)
        output_dir = payload.get("output_dir", "data/camera")
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f"camera_{uuid.uuid4().hex[:8]}.jpg")

        cap = cv2.VideoCapture(camera_index)
        try:
            if not cap.isOpened():
                return {
                    "status": "ERROR",
                    "available": False,
                    "reason": f"Camera index {camera_index} is not available or disconnected.",
                }

            ret, frame = cap.read()
            if not ret or frame is None:
                return {
                    "status": "ERROR",
                    "available": False,
                    "reason": f"Failed to read frame from camera index {camera_index}.",
                }

            cv2.imwrite(filepath, frame)
            h, w, _ = frame.shape
            logger.info(f"[VisionAgent] Camera frame captured ({w}x{h}) -> {filepath}")
            return {
                "status": "SUCCESS",
                "available": True,
                "filepath": filepath,
                "resolution": f"{w}x{h}",
                "result": f"Camera frame captured successfully: {filepath} ({w}x{h})",
            }
        finally:
            cap.release()

    def _run_ocr(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract text from specified image or active screen using OCR."""
        image_path = payload.get("filepath") or payload.get("image_path")
        
        # If no image path provided, capture screen first
        if not image_path:
            cap_res = self._capture_screen(payload)
            if cap_res.get("status") != "SUCCESS":
                return cap_res
            image_path = cap_res["filepath"]

        if not os.path.exists(image_path):
            return {
                "status": "ERROR",
                "available": False,
                "reason": f"Image file for OCR not found at path '{image_path}'.",
            }

        if not HAS_PIL:
            return {
                "status": "ERROR",
                "available": False,
                "reason": "Pillow (PIL) library unavailable for OCR processing.",
            }

        try:
            img = Image.open(image_path)
            extracted_text = ""
            
            if HAS_PYTESSERACT:
                try:
                    extracted_text = pytesseract.image_to_string(img).strip()
                except Exception as t_err:
                    logger.debug(f"[VisionAgent] Pytesseract execution notice: {t_err}")

            if not extracted_text:
                extracted_text = f"Image loaded from {image_path} ({img.width}x{img.height}). Text extraction returned empty."

            return {
                "status": "SUCCESS",
                "available": True,
                "filepath": image_path,
                "text": extracted_text,
                "result": f"OCR extracted text: {extracted_text}",
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "available": False,
                "reason": f"OCR extraction failed: {e}",
            }

    def _analyze_image(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze image or current screen content with structured output."""
        image_path = payload.get("filepath") or payload.get("image_path")
        prompt = payload.get("prompt") or payload.get("query") or "Describe what is visible in this image."

        if not image_path:
            cap_res = self._capture_screen(payload)
            if cap_res.get("status") != "SUCCESS":
                return cap_res
            image_path = cap_res["filepath"]

        if not os.path.exists(image_path):
            return {
                "status": "ERROR",
                "available": False,
                "reason": f"Image file not found at '{image_path}'.",
            }

        ocr_res = self._run_ocr({"filepath": image_path})
        raw_text = ocr_res.get("text", "")

        # Clean and structure OCR output
        cleaned_text = self._clean_ocr_text(raw_text)
        word_count = len(cleaned_text.split()) if cleaned_text else 0
        line_count = len(cleaned_text.splitlines()) if cleaned_text else 0

        # Detect potential UI elements from OCR patterns
        ui_elements = self._detect_ui_elements(cleaned_text)

        # Get image dimensions if PIL available
        dimensions = "unknown"
        if HAS_PIL:
            try:
                from PIL import Image
                img = Image.open(image_path)
                dimensions = f"{img.width}x{img.height}"
            except Exception:
                pass

        analysis_summary = (
            f"Screen Analysis of '{os.path.basename(image_path)}' ({dimensions}):\n"
            f"Prompt: {prompt}\n"
            f"OCR Text ({word_count} words, {line_count} lines):\n{cleaned_text[:500]}"
        )
        if ui_elements:
            analysis_summary += f"\n\nDetected UI elements: {', '.join(ui_elements)}"

        return {
            "status": "SUCCESS",
            "available": True,
            "filepath": image_path,
            "analysis": analysis_summary,
            "result": analysis_summary,
        }

    def _clean_ocr_text(self, text: str) -> str:
        """Clean and format OCR output for readability."""
        if not text:
            return ""
        import re
        # Remove excessive whitespace
        lines = text.splitlines()
        cleaned = []
        for line in lines:
            line = line.strip()
            if line:
                # Remove lines that are just special characters
                if re.sub(r'[^a-zA-Z0-9]', '', line):
                    cleaned.append(line)
        # Deduplicate consecutive identical lines
        deduped = []
        for line in cleaned:
            if not deduped or line != deduped[-1]:
                deduped.append(line)
        return "\n".join(deduped)

    def _detect_ui_elements(self, text: str) -> list:
        """Detect potential UI elements from OCR text patterns."""
        if not text:
            return []
        elements = []
        text_lower = text.lower()

        # Detect buttons
        button_words = ["button", "submit", "send", "cancel", "ok", "save", "delete"]
        for word in button_words:
            if word in text_lower:
                elements.append(f"button:{word}")

        # Detect input fields
        input_words = ["search", "type here", "enter", "input", "email", "password"]
        for word in input_words:
            if word in text_lower:
                elements.append(f"input:{word}")

        # Detect navigation
        nav_words = ["home", "menu", "back", "next", "settings", "profile"]
        for word in nav_words:
            if word in text_lower:
                elements.append(f"nav:{word}")

        # Detect links
        if "http" in text_lower or "www." in text_lower:
            elements.append("link:url_detected")

        return elements[:10]  # Cap at 10 elements
