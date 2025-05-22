from ..models import Vocabulary, WordList
from ..serializers import VocabularySerializer, WordListSerializer
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated


# input/output to the view should be in this form:
# {
#   "name": "Common Words",
#   "description": "Basic English words",
#   "words": [
#     {
#       "word": "backpack",
#       "definition": "a bag you wear on your back, with straps over your shoulders"
#       "image_url": "",
#       "video_url": "",
#     },
#     {
#       "word": "purse",
#       "definition": "a container used for carrying money and small personal items"
#       "image_url": "",
#       "video_url": "",
#     }
#   ]
# }

class WordListView(viewsets.ModelViewSet):
  queryset = WordList.objects.all()
  serializer_class = WordListSerializer
  permission_classes = [IsAuthenticated]
