from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..services import openrouter_service
from ..serializers import PromptSerializer

from google import genai
from google.genai import types

# payload format for:
# 
# Generate Definitions:
# {
#   "prompt": "Give 3 3rd grade academic dictionary definitions to guess the word \"INSERT_WORD_HERE\". Definitions should be distinct from words similar to it. Present the 3 clues in a JSON array format: [\"clue1\", \"clue2\", \"clue3\", \"clue4\", \"clue5\"].",
#   "system_message": "You are an expert in creating age-appropriate and distinct dictionary definitions for elementary school children. Focus on providing clear, simple, and accurate clues that highlight unique characteristics without directly revealing the word or words that sound similar. No need to add explanations, just give the definitions directly. Dont add string formatting, just plain text",
#   "temperature": 0.7,
#   "max_tokens": 200
# }

class GenAIView(APIView):
  def post(self, request, *args, **kwargs):
    serializer = PromptSerializer(data=request.data)
    if serializer.is_valid():
      prompt = serializer.validated_data.get('prompt')
      system_message = serializer.validated_data.get('system_message')
      temperature = serializer.validated_data.get('temperature')
      max_tokens = serializer.validated_data.get('max_tokens')

      try:
        # Use the OpenRouterService for non-streaming response
        response_data = openrouter_service.generate_text(
          prompt=prompt,
          system_message=system_message,
          temperature=temperature,
          max_tokens=max_tokens
        )
        # print(response_data)
        if response_data and 'choices' in response_data and len(response_data['choices']) > 0:
          generated_text = response_data["choices"][0]["message"]["content"]
          return Response({"response": generated_text}, status=status.HTTP_200_OK)
        else:
          return Response(
            {"error": "AI response format unexpected or service unavailable after retries."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE 
          )
      except Exception as e: # Catch any exceptions that bubble up from openrouter_service.generate_text
        # Log the full error for debugging
        print(f"Unhandled exception in ChatAPIView: {e}")
        return Response(
            {"error": "An unexpected error occurred while communicating with the AI service. Please try again later."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
  
class GenAICheckLimitView(APIView):
  def get(self, request):
    response_data = openrouter_service.check_limit()
    
    if response_data:
      generated_text = response_data["data"]
      return Response({"response": generated_text}, status=status.HTTP_200_OK)
    else:
      return Response(
        {"error": "Failed to establish connection with OpenRouter"},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
      )


DEFINITION_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "is_valid": {
            "type": "boolean",
            "description": "True if the word is a real dictionary word."
        },
        "definitions": {
            "type": "array",
            "description": "A list of 3 distinct 3rd-grade definitions, or an empty array if not valid.",
            "items": {
                "type": "string"
            }
        }
    },
    # Ensure all fields are required to prevent null values
    "required": ["is_valid", "definitions"],
    # Explicitly state the order
    "propertyOrdering": ["is_valid", "definitions"]
}

def generate_gemini_response(serializer, type):
  """
  Helper function to initialize Gemini AI.
  Will check if it is a generic AI prompt or for generating definitions.
  """
  # 1. Get data from serializer request
  prompt = serializer.validated_data.get('prompt')
  system_message = serializer.validated_data.get('system_message')
  if type == "DEFINITION":
    system_message = (
      "Respond STRICTLY according to the provided JSON schema."
      "Do not include any other text, markdown formatting, or explanation." 
      f"{system_message or ''}"
    )
  temperature = serializer.validated_data.get('temperature')
  max_tokens = serializer.validated_data.get('max_tokens')

  try:
    # 2. Initialize the Gemini Client
    client = genai.Client()

    # 3. Configure the Generation
    if type == "DEFINITION":
      config = types.GenerateContentConfig(
        system_instruction=system_message,
        temperature=temperature,
        max_output_tokens=1024,
        response_mime_type="application/json",
        response_schema=DEFINITION_OUTPUT_SCHEMA,
      )
    elif type == "GENERIC":
      config = types.GenerateContentConfig(
        system_instruction=system_message,
        temperature=temperature,
        max_output_tokens=1024,
      )
    
    # 4. Call the Gemini API
    response = client.models.generate_content(
      model="gemini-2.5-flash",
      contents=prompt,
      config=config
    )

    token_data = {
      "prompt_tokens": response.usage_metadata.prompt_token_count,
      "output_tokens": response.usage_metadata.candidates_token_count, 
      "total_tokens": response.usage_metadata.total_token_count
    }

    # 5. Determine the content to return based on the type
    if type == "DEFINITION":
      # Returns a Python dict/object (the structured JSON)
      response_data = response.parsed
    else: # type == "GENERIC"
      # Returns a string (the plain text)
      response_data = response.text

    # Handle cases where the model might be blocked or return no content
    if response_data is None:
      return Response(
        {"error": "Please try to generate again.", "tokens": token_data},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
      )

    return Response(
        {"response": response_data, "tokens": token_data},
        status=status.HTTP_200_OK
    )

  except Exception as e:
    # Handle API-specific or network errors
    return Response(
      {"error": f"Gemini API Error: {e}"},
      status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )

class GeminiAIGenericView(APIView):
  """
  use Gemini AI to make generic prompts.
  """
  def post(self, request):
    # Get validated data from the request
    serializer = PromptSerializer(data=request.data)
    if serializer.is_valid():
      return generate_gemini_response(serializer, "GENERIC")

    # Return validation errors if serializer is not valid
    return Response(
      serializer.errors,
      status=status.HTTP_400_BAD_REQUEST
    )


class GeminiAIDefinitionView(APIView):
  """
  use Gemini AI to make 3 definitions out of a word.
  """
  def post(self, request):
    # Get validated data from the request
    serializer = PromptSerializer(data=request.data)
    if serializer.is_valid():
      return generate_gemini_response(serializer, "DEFINITION")

    # Return validation errors if serializer is not valid
    return Response(
      serializer.errors,
      status=status.HTTP_400_BAD_REQUEST
    )
