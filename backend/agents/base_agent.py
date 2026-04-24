import json
import re
import os
import time
from dotenv import load_dotenv
from openai import OpenAI, APITimeoutError, APIConnectionError, APIStatusError

load_dotenv()

class AgentAPIError(Exception):
    """Wraps LLM API errors with a user-friendly message."""
    def __init__(self, user_message, detail=None):
        self.user_message = user_message
        self.detail = detail
        super().__init__(user_message)

class BaseAgent:
    def __init__(self, model=None):
        self.api_key = os.getenv("Z_AI_API_KEY", "")
        api_url = os.getenv("Z_AI_BASE_URL", "https://api.ilmu.ai/v1/chat/completions")

        # OpenAI client expects the base URL, not the full completions endpoint
        self.base_url = api_url.replace("/chat/completions", "") if api_url.endswith("/chat/completions") else api_url

        self.model = model or os.getenv("Z_AI_MODEL", "glm-4")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=180.0
        )

    @staticmethod
    def _friendly_error(e):
        """Convert API exceptions into user-friendly messages."""
        if isinstance(e, APITimeoutError):
            return AgentAPIError("The AI service timed out. Please try again with a shorter or simpler prompt.", detail=str(e))
        if isinstance(e, APIConnectionError):
            return AgentAPIError("Unable to reach the AI service. Please check your internet connection and try again.", detail=str(e))
        if isinstance(e, APIStatusError):
            code = e.status_code
            if code == 504 or code == 502:
                return AgentAPIError("The AI service is temporarily unavailable (gateway timeout). Please wait a moment and try again.", detail=str(e))
            if code == 429:
                return AgentAPIError("Too many requests. Please wait a moment and try again.", detail=str(e))
            if code == 401:
                return AgentAPIError("API key is invalid. Please check your configuration.", detail=str(e))
            if code >= 500:
                return AgentAPIError(f"The AI service returned an error (HTTP {code}). Please try again later.", detail=str(e))
            return AgentAPIError(f"AI service error (HTTP {code}). Please try again.", detail=str(e))
        if isinstance(e, AgentAPIError):
            return e
        return AgentAPIError("An unexpected error occurred. Please try again.", detail=str(e))

    @staticmethod
    def _extract_balanced_json(text, start):
        """
        Walk forward from `start` (which must point at '{' or '[') and return
        the substring that forms a complete, balanced JSON structure.
        If the structure is never closed (truncated output), returns everything
        from start to end so the repair logic can patch it.
        """
        opener = text[start]
        closer = '}' if opener == '{' else ']'
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch in ('{', '['):
                depth += 1
            elif ch in ('}', ']'):
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        # Never closed — return everything from start (truncated output)
        return text[start:]

    @staticmethod
    def _count_open_brackets(s):
        """Return a stack of unmatched openers in s, respecting string literals."""
        stack = []
        in_string = False
        escape = False
        for ch in s:
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch in ('{', '['):
                stack.append(ch)
            elif ch == '}' and stack and stack[-1] == '{':
                stack.pop()
            elif ch == ']' and stack and stack[-1] == '[':
                stack.pop()
        return stack

    @staticmethod
    def _parse_json_robust(text):
        """
        Parse JSON from LLM output, handling the most common failure modes:

        1. Markdown code fences  (```json ... ```)
        2. Markdown headers / bold before JSON  (**JSON:**, # Heading)
        3. JS-style comments      (// comment)
        4. Trailing LLM commentary after the JSON structure
        5. Python literals        (None → null, True → true, False → false)
        6. Unescaped control characters inside string values
        7. Trailing commas before } or ]
        8. Truncated output       (missing closing brackets / braces)
        9. Single-quoted strings  (simple cases)
        10. NaN / Infinity values
        11. Missing commas between } ] and { [
        """
        # ── Pre-processing ─────────────────────────────────────────────────────
        # Strip markdown code fences
        text = re.sub(r'```(?:json)?\s*', '', text).strip()
        text = re.sub(r'```\s*$', '', text).strip()

        # Strip markdown bold/headers that appear before the JSON
        text = re.sub(r'^\s*\*\*.*?\*\*\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*#{1,6}\s+.*$', '', text, flags=re.MULTILINE)
        text = text.strip()

        # Remove JS-style single-line comments (// ...)
        text = re.sub(r'//[^\n]*', '', text)

        # Locate the start of the outermost JSON structure
        obj_pos = text.find('{')
        arr_pos = text.find('[')
        if obj_pos == -1 and arr_pos == -1:
            raise ValueError(f"No JSON found in LLM output: {text[:300]}")
        if obj_pos == -1:
            start = arr_pos
        elif arr_pos == -1:
            start = obj_pos
        else:
            start = min(obj_pos, arr_pos)

        # Extract just the balanced JSON structure (ignores trailing LLM text)
        raw = BaseAgent._extract_balanced_json(text, start)

        # ── Helper: recursively replace NaN/Infinity in parsed objects ──────────
        def sanitize(obj):
            if isinstance(obj, float):
                if obj != obj or obj == float('inf') or obj == float('-inf'):
                    return None
                return obj
            if isinstance(obj, dict):
                return {k: sanitize(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [sanitize(v) for v in obj]
            return obj

        # ── Attempt 1: Parse the balanced extract as-is ────────────────────────
        try:
            return sanitize(json.loads(raw, parse_constant=lambda x: None))
        except json.JSONDecodeError:
            pass

        # ── Shared normalisation helper ─────────────────────────────────────────
        def normalise(s):
            s = re.sub(r'\bNone\b',  'null',  s)   # Python → JSON literals
            s = re.sub(r'\bTrue\b',  'true',  s)
            s = re.sub(r'\bFalse\b', 'false', s)
            s = re.sub(r'\bNaN\b',   'null',  s)   # NaN → null
            s = re.sub(r'\bInfinity\b', 'null', s)  # Infinity → null
            # Remove unescaped control chars (keep \t \n \r)
            s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', s)
            return s

        repaired = normalise(raw)

        # ── Attempt 2: After Python literal / control-char normalisation ────────
        try:
            return sanitize(json.loads(repaired, parse_constant=lambda x: None))
        except json.JSONDecodeError:
            pass

        # ── Attempt 3: Remove trailing commas before } or ] ────────────────────
        repaired = re.sub(r',\s*([}\]])', r'\1', repaired)

        # Insert missing commas between } or ] followed by { or [
        repaired = re.sub(r'([}\]])\s*([{\[])', r'\1,\2', repaired)

        try:
            return sanitize(json.loads(repaired, parse_constant=lambda x: None))
        except json.JSONDecodeError:
            pass

        # ── Attempt 4: Patch truncated output ──────────────────────────────────
        # Close any unclosed string
        quote_count = 0
        esc = False
        for ch in repaired:
            if esc:
                esc = False
                continue
            if ch == '\\':
                esc = True
                continue
            if ch == '"':
                quote_count += 1
        if quote_count % 2 == 1:
            repaired += '"'

        # Remove dangling partial tokens at the very end
        repaired = re.sub(r',\s*"[^"]*"\s*:\s*$', '', repaired)   # trailing "key":
        repaired = re.sub(r',\s*"[^"]*"\s*$',      '', repaired)   # trailing "key"
        repaired = re.sub(r',\s*$',                 '', repaired)   # trailing comma
        repaired = re.sub(r':\s*$',           ': null', repaired)   # trailing colon

        # Close unclosed brackets/braces (in reverse stack order)
        stack = BaseAgent._count_open_brackets(repaired)
        for opener in reversed(stack):
            repaired += '}' if opener == '{' else ']'

        # Remove any new trailing commas introduced by bracket-closing
        repaired = re.sub(r',\s*([}\]])', r'\1', repaired)

        try:
            return sanitize(json.loads(repaired, parse_constant=lambda x: None))
        except json.JSONDecodeError:
            pass

        # ── Attempt 5: Convert single quotes to double quotes ──────────────────
        try:
            sq_fixed = re.sub(r"(?<!\\)'", '"', repaired)
            return sanitize(json.loads(sq_fixed, parse_constant=lambda x: None))
        except (json.JSONDecodeError, Exception):
            pass

        raise ValueError(
            f"JSON repair failed after all attempts. "
            f"Raw output ({len(raw)} chars): {raw[:400]}..."
        )

    def query(self, system_prompt, user_prompt, format_json=True, max_retries=2, max_tokens=4096):
        """
        Query the LLM using STREAMING mode.

        Handles:
        - Truncation (finish_reason="length"): auto-retry with doubled max_tokens
        - Empty responses: retry
        - JSON parse failures: retry
        - API errors: retry with backoff
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        if not self.api_key or self.api_key == "your_zai_api_key_here":
            raise AgentAPIError("Missing valid API key. Please configure your .env file.")

        current_max_tokens = max_tokens
        last_error = None
        attempt = 0
        max_attempts = max_retries + 1 + 2  # extra room for truncation retries

        while attempt < max_attempts:
            try:
                text = ""
                finish_reason = None

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=current_max_tokens,
                    stream=True
                )

                for chunk in response:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if delta.content:
                            text += delta.content
                        if chunk.choices[0].finish_reason:
                            finish_reason = chunk.choices[0].finish_reason

                if finish_reason == "content_filter":
                    print(f"WARNING: {self.__class__.__name__} response filtered by API content filter")
                    raise ValueError("Response blocked by content filter.")

                # Truncation: retry with more tokens instead of accepting broken JSON
                if finish_reason == "length":
                    old_limit = current_max_tokens
                    current_max_tokens = min(current_max_tokens * 2, 16000)
                    if current_max_tokens > old_limit:
                        print(f"WARNING: {self.__class__.__name__} hit max_tokens={old_limit}, retrying with {current_max_tokens}")
                        attempt += 1
                        continue
                    else:
                        print(f"WARNING: {self.__class__.__name__} still truncated at max_tokens={current_max_tokens}")

                if not text.strip():
                    raise ValueError("LLM returned empty response.")

                if format_json:
                    try:
                        return self._parse_json_robust(text)
                    except ValueError as e:
                        print(f"JSON PARSE FAILED in {self.__class__.__name__}: {e}")
                        print(f"Raw output (first 500 chars): {text[:500]}")
                        raise
                return text

            except AgentAPIError:
                raise
            except (APITimeoutError, APIConnectionError, APIStatusError) as e:
                last_error = self._friendly_error(e)
                print(f"API Error in {self.__class__.__name__} (attempt {attempt + 1}): {e}")
                attempt += 1
                if attempt < max_attempts:
                    time.sleep(2)
            except ValueError as e:
                last_error = AgentAPIError(
                    "The AI returned an unexpected response format. Retrying...",
                    detail=str(e)
                )
                print(f"JSON parse error in {self.__class__.__name__} (attempt {attempt + 1}): {e}")
                attempt += 1
                if attempt < max_attempts:
                    time.sleep(1)
            except Exception as e:
                last_error = self._friendly_error(e)
                print(f"Error in {self.__class__.__name__} (attempt {attempt + 1}): {e}")
                attempt += 1
                if attempt < max_attempts:
                    time.sleep(2)

        raise last_error
