import requests
import json
from django.conf import settings

class OpenRouterService:
  def __init__(self, api_key):
    self.base_url = "https://openrouter.ai/api/v1/chat/completions"
    self.headers = {
      "Authorization": f"Bearer {api_key}",
      "Content-Type": "application/json",
    }
    self.model_name = "google/gemma-3-27b-it:free" # free version; remove ':free' if Openrouter account has credits

  def generate_text(self, prompt, system_message=None, temperature=0.7, max_tokens=500):
    messages = []
    if system_message:
      messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": prompt})

    payload = {
      "model": self.model_name,
      "messages": messages,
      "temperature": temperature,
      "max_tokens": max_tokens,
      "stream": False # Set to True for streaming responses
    }

    try:
      response = requests.post(self.base_url, headers=self.headers, data=json.dumps(payload))
      response.raise_for_status()  # Raise an exception for HTTP errors
      return response.json()
    except requests.exceptions.RequestException as e:
      print(f"Error calling OpenRouter API: {e}")
      return None

# Initialize the service with API key from settings
openrouter_service = OpenRouterService(api_key=settings.OPENROUTER_API_KEY)