from django.urls import path
from .views import *


urlpatterns = [
    path("", home_page_view),
    path("upload", upload_video),
    path("search", search_video_view),
    path("exists", check_video_exists),
]
