from ..models import Vocabulary, WordList
from ..serializers import VocabularySerializer, WordListSerializer
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny


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

  def get_queryset(self):
    user = self.request.user
    if user.role.name == 'teacher':
      return WordList.objects.filter(created_by=user)
    else:
      # Students can access wordlists from drills in their classrooms
      return WordList.objects.filter(
        drills__classroom__students=user,
        drills__status='published'
      ).distinct()
