from django.urls import path
from .views import *


urlpatterns = [
    path("", home_page_view),
    path("upload", upload_page_view),
    path("video", upload_video),
    path("search", search_video_view),
    path("exists", check_video_exists),
    # path("s3proxy/<path:file_path>", proxy_s3_file),
]
