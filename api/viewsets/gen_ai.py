from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..services import openrouter_service
from ..serializers import PromptSerializer

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



