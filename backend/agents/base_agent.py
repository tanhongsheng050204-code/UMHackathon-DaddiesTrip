import requests
import json
import re

class BaseAgent:
    def __init__(self, model="deepseek-r1:8b"):
        self.ollama_url = "http://127.0.0.1:11434/api/generate"
        self.model = model

    def query(self, system_prompt, user_prompt, format_json=True):
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "format": "json" if format_json else None,
            "options": {
                "num_predict": 4096,
                "temperature": 0.3
            }
        }

        try:
            response = requests.post(self.ollama_url, json=payload, timeout=300)
            response.raise_for_status()
            text = response.json().get("response", "")
            
            # Clean Deepseek thinking tags
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
            
            if format_json:
                json_match = re.search(r'(\{.*\})', text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(1))
                return json.loads(text)
            return text
        except Exception as e:
            print(f"Error in {self.__class__.__name__}: {e}")
            return None
