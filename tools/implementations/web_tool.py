"""
Web tool providing search, fetch, and HTTP request capabilities.

Three operations:
- search: Query Kagi search API for current information
- fetch: Compress webpage to faithful text extract via LLM (no options — URL in, text out)
- http: Make direct HTTP requests to APIs
"""
import re
from typing import Dict, Any, List, Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from tools.repo import Tool
from tools.registry import registry
from utils import http_client

try:
    from kagiapi import KagiClient
    KAGI_AVAILABLE = True
except ImportError:
    KAGI_AVAILABLE = False

try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False

try:
    from bs4 import BeautifulSoup, Comment
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


# --- Configuration ---

class WebToolConfig(BaseModel):
    """Configuration for web_tool."""
    enabled: bool = Field(default=True, description="Whether this tool is enabled")
    default_timeout: int = Field(default=30, description="Default timeout in seconds")
    max_timeout: int = Field(default=120, description="Maximum allowed timeout")
    # LLM config for content extraction (self-contained - not database-backed)
    llm_model: str = Field(default="openai/gpt-oss-120b", description="Model for content extraction")
    llm_endpoint: str = Field(default="https://api.groq.com/openai/v1/chat/completions", description="LLM endpoint")
    llm_api_key_name: Optional[str] = Field(default="subcortical_key", description="Vault key name for API key")


registry.register("web_tool", WebToolConfig)


# --- Input Models ---

class SearchInput(BaseModel):
    """Input for web search operation."""
    query: str = Field(..., min_length=1, description="Search query")
    max_results: int = Field(default=5, ge=1, le=20, description="Maximum results to return")
    allowed_domains: List[str] = Field(default_factory=list, description="Only include these domains")
    blocked_domains: List[str] = Field(default_factory=list, description="Exclude these domains")


class FetchInput(BaseModel):
    """Input for webpage fetch operation."""
    url: str = Field(..., description="URL to fetch")
    include_metadata: bool = Field(default=False, description="Include page metadata")
    timeout: Optional[int] = Field(default=None, ge=1, description="Request timeout in seconds")

    @field_validator("url")
    @classmethod
    def validate_url_scheme(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"URL must use http or https scheme, got: {parsed.scheme}")
        return v


class HttpInput(BaseModel):
    """Input for HTTP request operation."""
    method: Literal["GET", "POST", "PUT", "DELETE"] = Field(..., description="HTTP method")
    url: str = Field(..., description="Request URL")
    query_params: Optional[Dict[str, Any]] = Field(default=None, description="Query parameters")
    headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP headers")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Form data")
    json_body: Optional[Dict[str, Any]] = Field(default=None, description="JSON body")
    timeout: Optional[int] = Field(default=None, ge=1, description="Request timeout")
    response_format: Literal["json", "text", "full"] = Field(default="json", description="Response format")
    allowed_domains: List[str] = Field(default_factory=list, description="Only allow these domains")
    blocked_domains: List[str] = Field(default_factory=list, description="Block these domains")
    # Credential injection - allows LLM to reference stored credentials by name without seeing actual values
    credential_name: Optional[str] = Field(
        default=None,
        description="Name of stored API credential to use for authentication"
    )
    credential_header: str = Field(
        default="Authorization",
        description="HTTP header name to inject the credential into"
    )
    credential_prefix: str = Field(
        default="Bearer ",
        description="Prefix to prepend to credential value (e.g., 'Bearer ', 'token ', '')"
    )

    @field_validator("url")
    @classmethod
    def validate_url_scheme(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"URL must use http or https scheme, got: {parsed.scheme}")
        return v


# --- Tool Implementation ---

class WebTool(Tool):
    """
    Web tool combining search, fetch, and HTTP capabilities.

    Operations:
    - search: Query Kagi for current web information
    - fetch: URL in, compressed text out (fixed LLM extraction, no caller options)
    - http: Make direct HTTP requests to APIs
    """

    name = "web_tool"
    description = "Web search, fetch webpages, and HTTP requests"

    anthropic_schema = {
        "name": "web_tool",
        "description": "Search the web, fetch and extract webpage content, make HTTP requests to APIs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["search", "fetch", "http"],
                    "description": "'search' = web search, 'fetch' = compressed text extraction from a URL (no options — just pass url), 'http' = direct HTTP API request"
                },
                "query": {"type": "string", "description": "Web search query. Only used with operation='search'. Min 1 character"},
                "max_results": {"type": "integer", "description": "Number of search results to return (1-20, default 5). Ignored unless operation='search'"},
                "url": {"type": "string", "description": "HTTP or HTTPS URL to request. Required for 'fetch' and 'http'. Private/internal network addresses are blocked"},
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"], "description": "HTTP verb: GET, POST, PUT, or DELETE. Required for 'http' operation"},
                "query_params": {"type": "object", "description": "Key-value pairs appended as ?key=value query parameters. Only used with operation='http'"},
                "headers": {"type": "object", "description": "Custom HTTP request headers as {name: value} pairs. For 'http' operation. Do not set auth headers here — use credential_name instead"},
                "data": {"type": "object", "description": "Form-encoded request body (application/x-www-form-urlencoded). For 'http' only. Use json_body instead for JSON payloads"},
                "json_body": {"type": "object", "description": "JSON request body (application/json). For 'http' only. Use data instead for form-encoded payloads"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (min 1, max 120, default 30). For 'fetch' and 'http' operations"},
                "response_format": {"type": "string", "enum": ["json", "text", "full"], "description": "'json' (parse response as JSON, fall back to text), 'text' (raw response body), 'full' (body + sanitized headers + JSON if parseable). Default 'json'. For 'http' only"},
                "allowed_domains": {"type": "array", "items": {"type": "string"}, "description": "If set, only these domains are allowed (exact match or subdomain). Takes precedence over blocked_domains if both provided. For 'search' and 'http'"},
                "blocked_domains": {"type": "array", "items": {"type": "string"}, "description": "Domains to exclude (exact match or subdomain). Ignored if allowed_domains is also set. For 'search' and 'http'"},
                "include_metadata": {"type": "boolean", "description": "When true, adds 'title' and 'metadata' keys (content_type, byte size) to the fetch result. Default false"},
                "credential_name": {"type": "string", "description": "Name of a user-stored API credential to inject as an auth header. The credential value is retrieved server-side and never returned to you. For 'http' only"}
            },
            "required": ["operation"]
        }
    }

    # SSRF protection patterns
    _PRIVATE_NETWORK_PATTERNS = [
        r'^localhost$',
        r'^127\.',
        r'^10\.',
        r'^172\.(1[6-9]|2[0-9]|3[0-1])\.',
        r'^192\.168\.',
        r'^0\.0\.0\.0$',
        r'^\[::1\]$',
        r'^169\.254\.',
    ]

    # Response headers that should NEVER be returned to LLM (security)
    _SENSITIVE_RESPONSE_HEADERS = {
        'authorization', 'x-api-key', 'api-key', 'x-auth-token',
        'cookie', 'set-cookie', 'www-authenticate', 'proxy-authorization',
    }

    def __init__(self):
        super().__init__()
        self._kagi: Optional[KagiClient] = None
        self._init_kagi()

    def run(self, **params) -> Dict[str, Any]:
        """Route to appropriate operation handler."""
        operation = params.pop("operation", None)
        if not operation:
            raise ValueError("Required parameter 'operation' not provided")

        if operation == "search":
            return self._search(SearchInput(**params))
        elif operation == "fetch":
            return self._fetch(FetchInput(**params))
        elif operation == "http":
            return self._http(HttpInput(**params))
        else:
            raise ValueError(f"Unknown operation: {operation}. Must be: search, fetch, or http")

    # --- Search Operation ---

    def _search(self, input: SearchInput) -> Dict[str, Any]:
        """Execute web search with Kagi primary, DuckDuckGo fallback."""
        # Try Kagi first if available
        if self._kagi:
            try:
                response = self._kagi.search(input.query, limit=input.max_results)
                results = []
                for item in response.get("data", []):
                    url = item.get("url", "")
                    if self._should_include_url(url, input.allowed_domains, input.blocked_domains):
                        results.append({
                            "title": item.get("title", ""),
                            "url": url,
                            "snippet": item.get("snippet", "")
                        })
                return {"success": True, "results": results, "provider": "kagi"}
            except Exception as e:
                self.logger.warning(f"Kagi search failed: {e}, falling back to DuckDuckGo")

        # Fall back to DuckDuckGo
        if not DDGS_AVAILABLE:
            raise ValueError(
                "Web search requires either Kagi API key or DuckDuckGo. "
                "Install ddgs: pip install ddgs"
            )

        try:
            ddgs = DDGS()
            raw_results = ddgs.text(
                input.query,
                max_results=input.max_results,
                backend="auto"
            )

            if not raw_results:
                self.logger.warning(f"DuckDuckGo returned no results for query: {input.query}")

            results = []
            for item in raw_results:
                url = item.get("href", "")
                if self._should_include_url(url, input.allowed_domains, input.blocked_domains):
                    results.append({
                        "title": item.get("title", ""),
                        "url": url,
                        "snippet": item.get("body", "")
                    })

            return {"success": True, "results": results, "provider": "duckduckgo"}
        except Exception as e:
            self.logger.error(f"DuckDuckGo search error: {e}")
            raise ValueError(f"DuckDuckGo search failed: {e}")

    # --- Fetch Operation ---

    def _fetch(self, input: FetchInput) -> Dict[str, Any]:
        """Fetch webpage, clean HTML, compress to text via LLM."""
        self._validate_url(input.url)
        timeout = self._get_timeout(input.timeout)

        html, response_info = self._fetch_page(input.url, timeout)
        if html is None:
            return {"success": False, "url": input.url, **response_info}

        cleaned_html = self._clean_html(html)
        extracted = self._extract_with_llm(cleaned_html, input.url)

        result = {"success": True, "url": input.url, "content": extracted}

        if input.include_metadata:
            result["title"] = self._extract_title(html)
            result["metadata"] = {
                "content_type": response_info.get("content_type", "text/html"),
                "size": len(html),
            }

        return result

    def _fetch_page(self, url: str, timeout: int) -> tuple:
        """Fetch page via Playwright or HTTP fallback. Returns (html, info_dict)."""
        # Try Playwright first
        try:
            from utils.playwright_service import PlaywrightService
            playwright = PlaywrightService.get_instance()
            html = playwright.fetch_rendered_html(url, timeout=timeout)
            return html, {"content_type": "text/html"}
        except ImportError:
            self.logger.info("Playwright not available, using HTTP fallback")
        except RuntimeError as e:
            if "chromium" in str(e).lower() or "executable" in str(e).lower():
                self.logger.info("Chromium not installed, using HTTP fallback")
            else:
                return None, {"error": "playwright_error", "message": str(e)}
        except TimeoutError as e:
            return None, {"error": "timeout", "message": str(e)}
        except Exception as e:
            self.logger.warning(f"Playwright failed: {e}, trying HTTP fallback")

        # HTTP fallback for static pages
        try:
            response = http_client.get(
                url,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0 (compatible; MIRA/1.0)"},
                follow_redirects=True
            )
            response.raise_for_status()
            return response.text, {"content_type": response.headers.get("Content-Type", "text/html")}
        except http_client.TimeoutException:
            return None, {"error": "timeout", "message": f"Request timed out after {timeout}s"}
        except http_client.HTTPStatusError as e:
            return None, {"error": "http_error", "message": f"HTTP {e.response.status_code}"}
        except Exception as e:
            return None, {"error": "request_error", "message": str(e)}

    def _clean_html(self, html: str) -> str:
        """Remove scripts, styles, and non-content elements."""
        if not BS4_AVAILABLE:
            self.logger.warning("BeautifulSoup not available, returning raw HTML")
            return html

        soup = BeautifulSoup(html, "html.parser")

        # Remove non-content elements
        if soup.head:
            soup.head.decompose()
        for tag in soup.find_all(["script", "style", "noscript", "iframe", "object", "embed"]):
            tag.decompose()
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            comment.extract()

        return str(soup)

    # ~40k chars leaves room for system prompt + response within the 120B model's context
    _MAX_HTML_LENGTH = 40000

    # Fixed extraction prompt — no caller-directed options.
    # The extraction LLM is a compressor: faithful text selection with aggressive pruning.
    # Caller intelligence (instructions, focus) belongs in forage_tool, not here.
    _EXTRACTION_PROMPT = (
        "You are a text extractor. Output only text that appears on the page. "
        "Preserve: proper nouns, dates, numbers, prices, URLs, code, tables, lists. "
        "Preserve the page's original ordering. "
        "Drop: navigation, headers/footers, sidebars, ads, cookie banners, related links, boilerplate. "
        "No summaries. No introductions. No commentary. No interpretation. No added text. "
        "If content was truncated, extract what is present without noting the truncation."
    )

    def _extract_with_llm(self, html: str, url: str) -> str:
        """Compress cleaned HTML to faithful text via LLM."""
        from config import config
        from clients.vault_client import get_api_key
        from clients.llm_provider import LLMProvider

        tool_config = config.web_tool

        if tool_config.llm_api_key_name:
            api_key = get_api_key(tool_config.llm_api_key_name)
            if not api_key:
                raise RuntimeError(f"API key '{tool_config.llm_api_key_name}' not found in Vault")
        else:
            api_key = None

        truncated = False
        original_length = len(html)
        if original_length > self._MAX_HTML_LENGTH:
            html = html[:self._MAX_HTML_LENGTH]
            truncated = True
            self.logger.info(f"Truncated HTML from {original_length} to {self._MAX_HTML_LENGTH} chars")

        truncation_note = "\nContent was truncated." if truncated else ""
        system_prompt = f"{self._EXTRACTION_PROMPT}\n\nSource: {url}{truncation_note}"

        llm = LLMProvider(max_tokens=2048)
        response = llm.generate_response(
            messages=[{"role": "user", "content": f"```html\n{html}\n```"}],
            stream=False,
            endpoint_url=tool_config.llm_endpoint,
            model_override=tool_config.llm_model,
            api_key_override=api_key,
            system_override=system_prompt
        )

        extracted = llm.extract_text_content(response)
        if getattr(response, 'stop_reason', None) == "max_tokens":
            extracted += "\n\n[Extraction hit token limit — page content continues at source]"
        return extracted

    def _extract_title(self, html: str) -> str:
        """Extract page title from HTML."""
        match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else ""

    # --- HTTP Operation ---

    def _get_credential(self, credential_name: str) -> str:
        """
        Retrieve credential by name from UserCredentialService.

        The LLM specifies credentials by name; this method retrieves the actual
        value. The value is NEVER returned to the LLM - it's only used for
        HTTP header injection.

        Raises:
            ValueError: If credential does not exist
        """
        from utils.user_credentials import UserCredentialService

        credential_service = UserCredentialService()
        credential_value = credential_service.get_credential(
            credential_type="api_key",
            service_name=credential_name
        )

        if credential_value is None:
            raise ValueError(
                f"Credential '{credential_name}' not found. "
                f"Add it in Settings > API Credentials."
            )
        return credential_value

    def _http(self, input: HttpInput) -> Dict[str, Any]:
        """Make HTTP request with optional credential injection."""
        self._validate_url(input.url, input.allowed_domains, input.blocked_domains)
        timeout = self._get_timeout(input.timeout)

        # Build headers dict (copy to avoid mutating input)
        headers = dict(input.headers) if input.headers else {}
        injected_credential_header = None

        # Credential injection - LLM references by name, we inject actual value
        if input.credential_name:
            credential_value = self._get_credential(input.credential_name)
            headers[input.credential_header] = f"{input.credential_prefix}{credential_value}"
            injected_credential_header = input.credential_header
            self.logger.info(f"Injected credential '{input.credential_name}' into '{input.credential_header}'")

        # Build kwargs for the request
        kwargs = {
            "params": input.query_params,
            "headers": headers,
            "timeout": timeout,
            "follow_redirects": True
        }
        if input.data:
            kwargs["data"] = input.data
        if input.json_body:
            kwargs["json"] = input.json_body

        try:
            # Dispatch to appropriate http_client method
            method_map = {
                "GET": http_client.get,
                "POST": http_client.post,
                "PUT": http_client.put,
                "DELETE": http_client.delete
            }
            http_method = method_map[input.method]
            response = http_method(input.url, **kwargs)
        except http_client.TimeoutException:
            return {"success": False, "error": "timeout", "message": f"Timed out after {timeout}s"}
        except http_client.ConnectError as e:
            return {"success": False, "error": "connection_error", "message": str(e)}
        except http_client.HTTPStatusError as e:
            return {"success": False, "error": "http_error", "status_code": e.response.status_code, "message": str(e)}

        return self._format_http_response(response, input.response_format, injected_credential_header)

    def _format_http_response(
        self, response, format_type: str, injected_credential_header: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Format HTTP response based on requested format.

        Security: Sanitizes response headers to prevent credential leakage.
        Some APIs echo authentication headers back in responses - we strip
        those to ensure the LLM never sees credential values.
        """
        result = {
            "success": 200 <= response.status_code < 300,
            "status_code": response.status_code,
            "url": str(response.url)
        }

        if format_type == "json":
            try:
                result["data"] = response.json()
            except ValueError:
                result["data"] = response.text
                result["warning"] = "Response is not valid JSON"
        elif format_type == "text":
            result["data"] = response.text
        elif format_type == "full":
            result["data"] = response.text
            # Sanitize headers - remove sensitive ones to prevent credential leakage
            sanitized_headers = {
                k: v for k, v in response.headers.items()
                if k.lower() not in self._SENSITIVE_RESPONSE_HEADERS
                and not (injected_credential_header and k.lower() == injected_credential_header.lower())
            }
            result["headers"] = sanitized_headers
            try:
                result["json"] = response.json()
            except ValueError:
                pass

        return result

    # --- Helpers ---

    def _init_kagi(self) -> None:
        """Initialize Kagi client from vault."""
        if not KAGI_AVAILABLE:
            self.logger.info("Kagi library not available, will use DuckDuckGo for search")
            return

        try:
            from clients.vault_client import get_api_key
            api_key = get_api_key("kagi_api_key")
            if api_key:
                self._kagi = KagiClient(api_key)
                self.logger.info("Kagi client initialized")
            else:
                self.logger.info("Kagi API key not found, will use DuckDuckGo for search")
        except Exception as e:
            self.logger.warning(f"Failed to initialize Kagi: {e}, will use DuckDuckGo for search")

    def _get_timeout(self, timeout: Optional[int]) -> int:
        """Get validated timeout value."""
        from config import config
        try:
            default = config.web_tool.default_timeout
            max_timeout = config.web_tool.max_timeout
        except AttributeError:
            default, max_timeout = 30, 120

        if timeout is None:
            return default
        return min(timeout, max_timeout)

    def _validate_url(self, url: str, allowed: List[str] = None, blocked: List[str] = None) -> None:
        """Validate URL against SSRF protection and domain restrictions."""
        parsed = urlparse(url)
        # Use hostname (without port) for SSRF checks, netloc for domain matching
        hostname = (parsed.hostname or "").lower()
        domain = parsed.netloc.lower()

        # SSRF protection - always enforced (check hostname without port)
        for pattern in self._PRIVATE_NETWORK_PATTERNS:
            if re.match(pattern, hostname, re.IGNORECASE):
                raise ValueError(f"Blocked: private network access to {domain}")

        # Allowlist takes precedence
        if allowed:
            if not any(self._domain_matches(domain, d) for d in allowed):
                raise ValueError(f"Domain not in allowed list: {domain}")
        elif blocked:
            if any(self._domain_matches(domain, d) for d in blocked):
                raise ValueError(f"Domain blocked: {domain}")

    def _domain_matches(self, domain: str, pattern: str) -> bool:
        """Check if domain matches pattern (exact or subdomain)."""
        pattern = pattern.lower()
        return domain == pattern or domain.endswith("." + pattern)

    def _should_include_url(self, url: str, allowed: List[str], blocked: List[str]) -> bool:
        """Check if URL should be included in search results."""
        if not url:
            return False
        try:
            domain = urlparse(url).netloc.lower()
            if allowed:
                return any(self._domain_matches(domain, d) for d in allowed)
            if blocked:
                return not any(self._domain_matches(domain, d) for d in blocked)
            return True
        except Exception:
            return False
