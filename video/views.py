from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

# from django.core.files.storage import FileSystemStorage
# from django.http import HttpResponse
import subprocess

# import requests
import os
import boto3
from boto3.dynamodb.conditions import Key
import webvtt
import json

# from django.core.files.storage import default_storage


AWS_ACCESS_KEY_ID = os.getenv("access_key")
AWS_SECRET_ACCESS_KEY = os.getenv("secret_access_key")
AWS_REGION = os.getenv("AWS_REGION_NAME")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")


def home_page_view(request):
    return render(request, "index.html")


def upload_page_view(request):
    return render(request, "upload.html")


# videoName
@csrf_exempt
def upload_video(request):
    if request.method == "POST":
        if not "video" in request.FILES:
            return response_error(request, "No file found")
        video = request.FILES["video"]
        video_name = video.name
        with open(f"temp/{video_name}", "wb") as temp:
            for chunk in video.chunks():
                temp.write(chunk)
        print("upload done the server")
        subprocess.run(
            [
                "ccextractor",
                "temp/" + video_name,
                "-o",
                "subtitles/" + video_name + ".srt",
            ]
        )
        srt_file = "subtitles/" + video_name + ".srt"
        file_size = os.path.getsize(srt_file)
        if file_size == 0:
            return response_error(request, "No subtitle found in video")

        vvt_file = "subtitles/" + video_name + ".vtt"
        captions = webvtt.from_srt(srt_file)
        captions.save(vvt_file)

        subprocess.run(
            [
                "webvtt-to-json",
                "subtitles/" + video_name + ".vtt",
                "-o",
                "subtitles/" + video_name + ".json",
            ]
        )

        upload_to_dynomodb(video_name)
        upload_to_s3("temp/" + video_name, False)
        upload_to_s3("subtitles/" + video_name + ".vtt", True)
        remove_file(video_name)
        return search_dynamodb(request, video_name)
    return response_error(request, "Only method post allow at this url")


def search_video_view(request):
    return render(request, "search.html")


@csrf_exempt
def check_video_exists(request):
    if request.method == "POST":
        video_name = request.POST.get("search")
        return search_dynamodb(request, video_name)
    return response_error(request, "Post method only allow")


def search_dynamodb(request, video_name):
    session = boto3.Session(
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )
    dynamodb = session.resource("dynamodb")
    table = dynamodb.Table("djago-local")

    try:
        response = table.query(KeyConditionExpression=Key("videoName").eq(video_name))
        result = response.get("Items", [])[0]
        if response.get("Count", 0) != 0:
            print(f"Video '{result.get("videoName", [])}' exists.")
            value = {
                "s3_video": s3_url("temp/" + video_name, False),
                "s3_subtitle": s3_url("subtitles/" + video_name + ".vtt", True),
                "subtitle": result.get("subtitles", []),
            }
            return render(request, "video.html", value)
        else:
            print(f"Video '{result.videoName}' does not exist.")
            return response_error(request, "Video does not exists")

    except Exception as e:
        print("Error querying item:", str(e))
        return response_error(request, "Internal server Error")


def response_error(request, error_str):
    err = {"error": error_str}
    return render(request, "error.html", err)


def upload_to_dynomodb(video_name):
    access_key = os.getenv("access_key")
    secret_access_key = os.getenv("secret_access_key")
    session = boto3.Session(
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )
    video_name = video_name
    dynamodb = session.resource("dynamodb")
    table = dynamodb.Table("djago-local")

    with open("subtitles/" + video_name + ".json", "r") as json_file:
        subtitles = json.load(json_file)

    try:
        response = table.put_item(
            Item={"videoName": video_name, "subtitles": subtitles}
        )
    except Exception as e:
        print("Error adding item:", str(e))
    print("✅done uploading to dynamodb :")


#
# @csrf_exempt
# def proxy_s3_file(request, file_path):
#     s3_url = (
#         f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{file_path}"
#     )
#     response = requests.get(s3_url)
#
#     if response.status_code == 200:
#         content_type = response.headers.get("Content-Type", "application/octet-stream")
#         return HttpResponse(response.content, content_type=content_type)
#     else:
#         return HttpResponse(status=response.status_code)


def upload_to_s3(name, sub):
    session = boto3.Session(
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )
    s3_client = session.resource("s3")
    print("connect to s3")
    if not sub:
        result = s3_client.Bucket(AWS_STORAGE_BUCKET_NAME).upload_file(name, name)
    else:
        sub = name.split(".")[0] + ".vtt"
        result = s3_client.Bucket(AWS_STORAGE_BUCKET_NAME).upload_file(name, sub)
    print("upload done")


def s3_url(video_name, sub):
    if not sub:
        pre_signed_url_video = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{video_name}"
    else:
        sub = video_name.split(".")[0] + ".vtt"
        pre_signed_url_video = (
            f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{sub}"
        )
    return pre_signed_url_video


def remove_file(video_name):
    if os.path.isfile("temp/" + video_name):
        os.remove("temp/" + video_name)
    if os.path.isfile("subtitles/" + video_name + ".vtt"):
        os.remove("subtitles/" + video_name + ".vtt")
    if os.path.isfile("subtitles/" + video_name + ".json"):
        os.remove("subtitles/" + video_name + ".json")
    if os.path.isfile("subtitles/" + video_name + ".srt"):
        os.remove("subtitles/" + video_name + ".srt")
