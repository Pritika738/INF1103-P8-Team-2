# app/infrastructure/ai_manager.py
import json
import time
from typing import Type
from pydantic import BaseModel
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from config import AI_MODEL_NAME, get_api_key, BASE_DELAY, AI_MAX_RETRIES

class AIManager:
    def __init__(self):
        # get API
        self.api_key = get_api_key()
        if not self.api_key:
            return json.dumps({"error": "AI API key not configured."})

        # variables from config.py
        self.model = AI_MODEL_NAME
        self.delay = BASE_DELAY
        self.retries = AI_MAX_RETRIES


    def call_ai_structured(self, file_bytes: bytes, mime_type: str, prompt: str, schema: Type[BaseModel]) -> str:

        attempt = 0
        current_delay = self.delay
        last_error_msg = "Unknown infrastructure failure"

        while attempt < self.retries:
            try:
                content_parts = [
                    types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                    types.Part.from_text(text=prompt)
                ]

                client = genai.Client(api_key=self.api_key)
                response = client.models.generate_content(
                    model=self.model,
                    contents=content_parts,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema, # Constrained dynamically by Gemini natively
                        temperature=0.1
                    )
                )
                
                if not response or not getattr(response, "text", None):
                    last_error_msg = "The AI service returned an empty response."
                    attempt += 1
                    time.sleep(current_delay)
                    current_delay *= 2
                    continue
                    
                return response.text

            except genai_errors.APIError as api_err:
                last_error_msg = f"Gemini API Error ({api_err.code}): {api_err.message}"
                attempt += 1
                if attempt < self.retries:
                    time.sleep(current_delay)
                    current_delay *= 2
                    
            except Exception as e:
                # This is where your old code caught "AttributeError: 'list' object has no attribute 'strip'"
                last_error_msg = f"Unexpected engine error: {str(e)}"
                attempt += 1
                if attempt < self.retries:
                    time.sleep(current_delay)
                    current_delay *= 2

        # If all retries fail, return a structured error block
        return json.dumps({
            "error": f"AI Generation failed. Last error details: {last_error_msg}"
        })

    def call_ai_structured_no_file(self, prompt: str, schema: Type[BaseModel]) -> str:
        attempt = 0
        current_delay = self.delay
        last_error_msg = "Unknown infrastructure failure"
        while attempt < self.retries:
            try:
                client = genai.Client(api_key=self.api_key)
                response = client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema,
                        temperature=0.1
                    )
                )
                if not response or not getattr(response, "text", None):
                    last_error_msg = "The AI service returned an empty response."
                    attempt += 1
                    time.sleep(current_delay)
                    current_delay *= 2
                    continue
                    
                return response.text

            except genai_errors.APIError as api_err:
                last_error_msg = f"Gemini API Error ({api_err.code}): {api_err.message}"
                attempt += 1
                if attempt < self.retries:
                    time.sleep(current_delay)
                    current_delay *= 2
                    
            except Exception as e:
                # This is where your old code caught "AttributeError: 'list' object has no attribute 'strip'"
                last_error_msg = f"Unexpected engine error: {str(e)}"
                attempt += 1
                if attempt < self.retries:
                    time.sleep(current_delay)
                    current_delay *= 2
        return json.dumps({
            "error": f"AI Generation failed. Last error details: {last_error_msg}"
        })
ai_manager = AIManager()
