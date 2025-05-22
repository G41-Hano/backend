import os
import json
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
from rest_framework.permissions import IsAuthenticated, AllowAny

WORDLISTS_DIR = os.path.join(settings.BASE_DIR, 'api', 'word-lists')

# for fetching all summaries of word lists (id, name, and description)
class BuiltInWordListIndexView(APIView):
  permission_classes = [AllowAny]

  def get(self, request):
    wordlists_summary = []

    for filename in os.listdir(WORDLISTS_DIR):
      if filename.endswith('.json'):
        file_path = os.path.join(WORDLISTS_DIR, filename)
        with open(file_path, 'r', encoding='utf-8') as f:
          try:
            data = json.load(f)
            summary = {
              "id": data.get("id"),
              "name": data.get("name"),
              "description": data.get("description", "")
            }
            wordlists_summary.append(summary)
          except Exception as e:
            # Optionally log error and skip
            print("No file found with name: " + filename)
            continue

    return Response(wordlists_summary)


# for fetching 1 word list AND its words
class BuiltInWordListView(APIView):
  permission_classes = [AllowAny]

  def get(self, request, list_id):
    file_path = os.path.join(WORDLISTS_DIR, f'{list_id}.json')
    
    if not os.path.exists(file_path):
      return Response({"error": "Word list not found."}, status=404)
    
    with open(file_path, 'r', encoding='utf-8') as f:
      data = json.load(f)

    return Response(data)
