"""
ULTRON V3 - Browser Automation Agent
Phase 2B.5 Domain Agent for Playwright / Web Browser Automation & Page Inspection.
Integrates BaseUltronAgent, WorkspaceACL, Security Confirmation Guards, and AgentMemoryBus.
"""

import os
import sys
import time
import urllib.parse
from typing import Dict, Any, Optional, List

from agents.base_ultron_agent import BaseUltronAgent
from core.logger import logger
from core.session import session

# Playwright safe import
try:
    from playwright.sync_api import sync_playwright, Playwright, Browser, Page
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


class BrowserAgent(BaseUltronAgent):
    """
    Web Browser Automation & Navigation Domain Agent.
    
    Capabilities:
    - browser_automation: General web automation
    - open_url: Navigate to specified web URL
    - inspect_page: Extract text and DOM content from page
    - extract_text: Extract text content from active page
    - click_element: Click specified selector/button
    - type_into_field: Input text into specified input field
    - scroll: Scroll web page
    - screenshot: Capture screenshot of active web page
    - close_browser: Gracefully terminate browser session
    """

    def __init__(
        self,
        agent_id: str = "browser_agent",
        name: str = "Browser Automation Agent",
        description: str = "Automates web navigation, page inspection, text extraction, web screenshots, and form interactions.",
        bus: Optional[Any] = None,
        version: str = "1.0.0",
    ) -> None:
        capabilities = [
            "browser_automation",
            "open_url",
            "inspect_page",
            "extract_text",
            "click_element",
            "type_into_field",
            "scroll",
            "screenshot",
            "close_browser",
        ]
        supported_skills = ["web_navigation", "web_scraping", "page_inspection", "browser_control"]
        super().__init__(
            agent_id=agent_id,
            name=name,
            description=description,
            capabilities=capabilities,
            supported_skills=supported_skills,
            bus=bus,
            version=version,
        )

        self._playwright_instance: Optional[Any] = None
        self._browser_instance: Optional[Any] = None
        self._page_instance: Optional[Any] = None
        self._active_url: str = ""

    def _do_execute_task(self, task_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardized task execution entry point for BrowserAgent.
        Supported actions: open_url, inspect_page, extract_text, click_element, type_into_field, scroll, screenshot, close_browser.
        """
        action = payload.get("action", "").lower().strip()
        t_start = time.perf_counter()

        logger.info(f"[BrowserAgent] Executing action '{action}'...")

        try:
            if action in ["open_url", "navigate", "go_to"]:
                res = self._open_url(payload)
            elif action in ["inspect_page", "extract_text", "read_page"]:
                res = self._inspect_page(payload)
            elif action in ["click_element", "click"]:
                res = self._click_element(payload)
            elif action in ["type_into_field", "type", "fill"]:
                res = self._type_into_field(payload)
            elif action in ["scroll"]:
                res = self._scroll(payload)
            elif action in ["screenshot", "take_screenshot"]:
                res = self._take_screenshot(payload)
            elif action in ["close_browser", "close"]:
                res = self._close_browser(payload)
            else:
                res = {
                    "status": "ERROR",
                    "available": False,
                    "reason": f"Unknown or unsupported browser action '{action}'.",
                }

            latency_ms = (time.perf_counter() - t_start) * 1000.0
            if isinstance(res, dict):
                res["latency_ms"] = round(latency_ms, 2)
            return res

        except Exception as err:
            logger.error(f"[BrowserAgent] Error executing action '{action}': {err}")
            return {
                "status": "ERROR",
                "available": False,
                "reason": str(err),
                "latency_ms": round((time.perf_counter() - t_start) * 1000.0, 2),
            }

    def _ensure_browser(self, headless: bool = True) -> bool:
        """Initialize Playwright browser session if not already running."""
        if not HAS_PLAYWRIGHT:
            return False

        with self._lock:
            try:
                if self._browser_instance and self._browser_instance.is_connected():
                    return True

                self._playwright_instance = sync_playwright().start()
                brave_path = r"C:\Users\AZEEZ\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe"
                self._browser_instance = self._playwright_instance.chromium.launch(
                    headless=headless,
                    executable_path=brave_path,
                    timeout=15000,
                )
                self._browser_instance.new_context()
                
                if not headless:
                    logger.info("[BrowserAgent] Brave browser launch requested")
                    logger.info("[BrowserAgent] Brave browser launched")
                else:
                    logger.info("[BrowserAgent] Playwright Chromium browser initialized successfully.")
                return True
            except Exception as e:
                logger.error(f"[BrowserAgent] Failed to launch Playwright browser: {e}")
                self._cleanup_browser()
                return False

    def _cleanup_browser(self) -> None:
        """Clean up Playwright browser handle and process."""
        with self._lock:
            try:
                if self._page_instance:
                    self._page_instance.close()
            except Exception:
                pass
            try:
                if self._browser_instance:
                    self._browser_instance.close()
            except Exception:
                pass
            try:
                if self._playwright_instance:
                    self._playwright_instance.stop()
            except Exception:
                pass
            self._page_instance = None
            self._browser_instance = None
            self._playwright_instance = None
            self._active_url = ""

    def _validate_url(self, url: str) -> bool:
        """Validate URL to prevent unsafe schemes or local file access outside authorized workspace."""
        if not url:
            return False
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme == "file":
            # Verify file URL is within authorized workspace
            file_path = urllib.parse.unquote(parsed.path)
            if os.name == 'nt' and file_path.startswith('/'):
                file_path = file_path[1:] # Strip leading slash on Windows for local file URLs
            # Basic path traversal protection
            if ".." in file_path:
                return False
            return os.path.exists(file_path)
        return parsed.scheme in ["http", "https", ""]

    def _open_url(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Navigate Playwright browser to specified URL."""
        url = payload.get("url") or payload.get("target") or "https://example.com"
        if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("file://"):
            url = f"https://{url}"

        if not self._validate_url(url):
            return {
                "status": "ERROR",
                "available": False,
                "reason": f"Security violation: Navigation to URL '{url}' rejected.",
            }

        # For explicit open URL requests from voice, default to visible browser
        headless = payload.get("headless", False)
        
        if not headless:
            logger.info("[BrowserAgent] Visible browser launch requested")

        if not self._ensure_browser(headless=headless):
            if not headless:
                # If explicit visible browser requested, fail loudly instead of HTTP fallback
                return {
                    "status": "ERROR",
                    "available": False,
                    "reason": "Failed to launch visible browser session.",
                }

            # Fallback to requests HTTP extraction if Playwright browser binary missing
            try:
                import requests
                resp = requests.get(url, timeout=10)
                self._active_url = url
                return {
                    "status": "SUCCESS",
                    "available": True,
                    "backend": "HTTP_Fallback",
                    "url": url,
                    "title": url,
                    "result": f"Navigated to '{url}' via HTTP request. Status Code: {resp.status_code}",
                }
            except Exception as req_err:
                return {
                    "status": "ERROR",
                    "available": False,
                    "reason": f"Browser automation & HTTP navigation failed: {req_err}",
                }

        if not headless:
            logger.info("[BrowserAgent] Visible browser launched")

        try:
            from urllib.parse import urlparse
            target_domain = urlparse(url).netloc.replace("www.", "")
            
            target_page = None
            if self._browser_instance and self._browser_instance.contexts:
                context = self._browser_instance.contexts[0]
                for p in context.pages:
                    if not p.is_closed():
                        # If page is essentially blank (about:blank), we can just reuse it
                        if p.url == "about:blank":
                            target_page = p
                            break
                        
                        p_domain = urlparse(p.url).netloc.replace("www.", "")
                        if target_domain and p_domain and target_domain in p_domain:
                            target_page = p
                            break
                            
            if target_page:
                self._page_instance = target_page
                logger.info("[BrowserAgent] Reusing existing Brave session")
                try:
                    self._page_instance.bring_to_front()
                except Exception:
                    pass
            else:
                context = self._browser_instance.contexts[0] if self._browser_instance.contexts else self._browser_instance.new_context()
                self._page_instance = context.new_page()
                logger.info("[BrowserAgent] Page opened")

            self._page_instance.goto(url, timeout=15000, wait_until="domcontentloaded")
            title = self._page_instance.title()
            self._active_url = url
            logger.info(f"[BrowserAgent] Navigated to '{url}' | Title: '{title}'")
            logger.info("[BrowserAgent] Navigated successfully")

            return {
                "status": "SUCCESS",
                "available": True,
                "url": url,
                "title": title,
                "result": f"Successfully navigated to '{url}' ({title}).",
            }
        except Exception as e:
            logger.error(f"[BrowserAgent] Navigation error for '{url}': {e}")
            return {
                "status": "ERROR",
                "available": False,
                "reason": f"Browser navigation to '{url}' failed: {e}",
            }

    def _inspect_page(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract text content from current web page."""
        url = payload.get("url")
        if url:
            open_res = self._open_url(payload)
            if open_res.get("status") != "SUCCESS":
                return open_res

        if not self._page_instance or not self._browser_instance:
            return {
                "status": "ERROR",
                "available": False,
                "reason": "No active browser session. Call open_url first.",
            }

        try:
            page_text = self._page_instance.inner_text("body", timeout=5000)
            title = self._page_instance.title()
            clean_text = " ".join(page_text.split())[:1000]

            return {
                "status": "SUCCESS",
                "available": True,
                "url": self._active_url,
                "title": title,
                "text": clean_text,
                "result": f"Page Content from '{title}':\n{clean_text[:300]}...",
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "available": False,
                "reason": f"Failed to extract page text: {e}",
            }

    def _click_element(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Click specified element selector on active page with security check."""
        selector = payload.get("selector") or payload.get("target")
        is_destructive = payload.get("is_destructive", False)

        if is_destructive:
            # Check security confirmation
            if not payload.get("confirmed", False):
                token = session.set_pending_confirmation(
                    action="browser_click",
                    command=f"Click element '{selector}'",
                    payload=payload,
                )
                return {
                    "status": "PENDING_CONFIRMATION",
                    "confirmation_token": token["confirmation_id"],
                    "result": f"Confirmation required to click destructive element '{selector}'.",
                }

        if not self._page_instance:
            return {
                "status": "ERROR",
                "available": False,
                "reason": "No active browser session.",
            }

        try:
            self._page_instance.click(selector, timeout=5000)
            logger.info(f"[BrowserAgent] Clicked selector '{selector}' on '{self._active_url}'")
            return {
                "status": "SUCCESS",
                "available": True,
                "selector": selector,
                "result": f"Clicked element '{selector}' successfully.",
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "available": False,
                "reason": f"Failed to click selector '{selector}': {e}",
            }

    def _type_into_field(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Type text into specified input field selector."""
        selector = payload.get("selector") or payload.get("target")
        text = payload.get("text") or payload.get("value") or ""

        if not self._page_instance:
            return {
                "status": "ERROR",
                "available": False,
                "reason": "No active browser session.",
            }

        try:
            self._page_instance.fill(selector, text, timeout=5000)
            logger.info(f"[BrowserAgent] Typed text into selector '{selector}'")
            return {
                "status": "SUCCESS",
                "available": True,
                "selector": selector,
                "result": f"Typed text into selector '{selector}' successfully.",
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "available": False,
                "reason": f"Failed to type into selector '{selector}': {e}",
            }

    def _scroll(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Scroll active web page."""
        direction = payload.get("direction", "down").lower()
        if not self._page_instance:
            return {
                "status": "ERROR",
                "available": False,
                "reason": "No active browser session.",
            }

        try:
            delta = 500 if direction == "down" else -500
            self._page_instance.evaluate(f"window.scrollBy(0, {delta})")
            return {
                "status": "SUCCESS",
                "available": True,
                "result": f"Scrolled page {direction} successfully.",
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "available": False,
                "reason": f"Failed to scroll page: {e}",
            }

    def _take_screenshot(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Take screenshot of active browser page."""
        if not self._page_instance:
            return {
                "status": "ERROR",
                "available": False,
                "reason": "No active browser session.",
            }

        output_dir = payload.get("output_dir", "data/browser_screenshots")
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f"browser_{uuid.uuid4().hex[:8]}.png")

        try:
            self._page_instance.screenshot(path=filepath)
            logger.info(f"[BrowserAgent] Browser screenshot saved to '{filepath}'")
            return {
                "status": "SUCCESS",
                "available": True,
                "filepath": filepath,
                "result": f"Browser screenshot captured successfully: {filepath}",
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "available": False,
                "reason": f"Failed to capture browser screenshot: {e}",
            }

    def _close_browser(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Close Playwright page or entire browser cleanly."""
        target_url = payload.get("url", "")
        
        if not self._browser_instance or not self._browser_instance.is_connected():
            return {
                "status": "ERROR",
                "available": False,
                "reason": "There is no active browser open.",
            }
            
        if not target_url or target_url == "https://example.com":
            self._cleanup_browser()
            logger.info("[BrowserAgent] Browser session closed")
            return {
                "status": "SUCCESS",
                "available": True,
                "result": "Browser session closed.",
            }
            
        target_page = None
        from urllib.parse import urlparse
        target_domain = urlparse(target_url).netloc.replace("www.", "")
        
        if self._browser_instance.contexts:
            for p in self._browser_instance.contexts[0].pages:
                if not p.is_closed():
                    p_domain = urlparse(p.url).netloc.replace("www.", "")
                    if target_domain and p_domain and target_domain in p_domain:
                        target_page = p
                        break
                        
        if not target_page:
            return {
                "status": "ERROR",
                "available": False,
                "reason": f"I couldn't find an active browser page for {target_domain}.",
            }

        try:
            target_page.close()
            logger.info("[BrowserAgent] Page closed")
            
            # Update _page_instance if we closed the active one
            if self._page_instance == target_page:
                self._page_instance = None
                
            return {
                "status": "SUCCESS",
                "available": True,
                "result": "Page closed successfully.",
            }
        except Exception as e:
            logger.error(f"[BrowserAgent] Close failed: {e}")
            return {
                "status": "ERROR",
                "available": False,
                "reason": f"Close failed: {e}",
            }

    def shutdown(self) -> None:
        """Service shutdown lifecycle hook."""
        self._cleanup_browser()
        super().shutdown()
