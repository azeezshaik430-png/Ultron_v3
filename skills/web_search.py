"""
ULTRON V3
Web Search Skill

Searches the web using DuckDuckGo HTML API.
No API key required. Uses httpx for HTTP requests.
Returns structured results with title, URL, and snippet.
"""

import re
import html
from typing import Dict, Any, List, Optional
from core.logger import logger


def search_web(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Search the web using DuckDuckGo HTML endpoint.
    
    Returns:
        {
            "status": "SUCCESS" | "ERROR",
            "query": str,
            "results": [{"title": str, "url": str, "snippet": str}],
            "result_count": int,
            "answer": str | None  # DuckDuckGo instant answer if available
        }
    """
    if not query or not query.strip():
        return {
            "status": "ERROR",
            "query": query,
            "results": [],
            "result_count": 0,
            "error": "Empty search query",
        }

    query = query.strip()
    logger.info(f"[WebSearch] Searching: '{query}'")

    try:
        import httpx

        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        data = {"q": query}

        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.post(url, data=data, headers=headers)
            response.raise_for_status()

        results = _parse_html_results(response.text, max_results)
        answer = _extract_instant_answer(response.text)

        logger.info(f"[WebSearch] Found {len(results)} results for '{query}'")

        return {
            "status": "SUCCESS",
            "query": query,
            "results": results,
            "result_count": len(results),
            "answer": answer,
        }

    except ImportError:
        logger.error("[WebSearch] httpx not installed")
        return {
            "status": "ERROR",
            "query": query,
            "results": [],
            "result_count": 0,
            "error": "httpx library not available",
        }
    except httpx.TimeoutException:
        logger.warning(f"[WebSearch] Timeout searching for '{query}'")
        return {
            "status": "ERROR",
            "query": query,
            "results": [],
            "result_count": 0,
            "error": "Search timed out",
        }
    except Exception as e:
        logger.error(f"[WebSearch] Search error: {e}")
        return {
            "status": "ERROR",
            "query": query,
            "results": [],
            "result_count": 0,
            "error": str(e),
        }


def _parse_html_results(html_content: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Parse DuckDuckGo HTML search results page."""
    results = []

    # Find result blocks — DuckDuckGo HTML uses class="result__a" for links
    # and class="result__snippet" for snippets
    link_pattern = re.compile(
        r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        re.DOTALL,
    )
    snippet_pattern = re.compile(
        r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
        re.DOTALL,
    )

    links = link_pattern.findall(html_content)
    snippets = snippet_pattern.findall(html_content)

    for i in range(min(len(links), max_results)):
        raw_url, raw_title = links[i]
        raw_snippet = snippets[i] if i < len(snippets) else ("", "")

        # Clean HTML entities and tags
        title = _clean_html(raw_title)
        snippet = _clean_html(raw_snippet if isinstance(raw_snippet, tuple) else raw_snippet)

        # Extract actual URL from DuckDuckGo redirect
        url = _extract_url(raw_url)

        if title and url:
            results.append({
                "title": title,
                "url": url,
                "snippet": snippet[:300] if snippet else "",
            })

    return results


def _extract_url(ddg_url: str) -> str:
    """Extract actual URL from DuckDuckGo redirect URL."""
    # DuckDuckGo wraps URLs in redirects like //duckduckgo.com/l/?uddg=...
    if "uddg=" in ddg_url:
        match = re.search(r'uddg=([^&]+)', ddg_url)
        if match:
            from urllib.parse import unquote
            return unquote(match.group(1))

    # If it's already a direct URL
    if ddg_url.startswith("http"):
        return ddg_url

    # Protocol-relative URL
    if ddg_url.startswith("//"):
        return "https:" + ddg_url

    return ddg_url


def _extract_instant_answer(html_content: str) -> Optional[str]:
    """Extract DuckDuckGo instant answer if available."""
    match = re.search(
        r'<div[^>]*class="zci__main-content"[^>]*>(.*?)</div>',
        html_content,
        re.DOTALL,
    )
    if match:
        answer = _clean_html(match.group(1))
        if answer and len(answer) > 10:
            return answer[:500]
    return None


def _clean_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    if not text:
        return ""
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', str(text))
    # Decode HTML entities
    clean = html.unescape(clean)
    # Normalize whitespace
    clean = ' '.join(clean.split())
    return clean.strip()
