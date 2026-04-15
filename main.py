from fastapi import FastAPI, Response # Response 추가
from fastapi.responses import PlainTextResponse # PlainTextResponse 추가
import requests
import json
import os
import re
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io

app = FastAPI()

# 👉 구글 드라이브 폴더 ID
FOLDER_ID = "1Mh3gAlf63tq5_oiKAP4k-d5FAHbA6Z6o"

def clean_text(raw_html):
    if not raw_html: return ""
    clean = re.sub(r'<[^>]*>', ' ', raw_html)
    clean = re.sub(r'\?.*?\?', '', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

def get_drive_service():
    creds_json = os.environ.get("GOOGLE_USER_CREDENTIALS")
    if not creds_json:
        raise Exception("환경변수 GOOGLE_USER_CREDENTIALS를 찾을 수 없습니다.")
    creds_info = json.loads(creds_json)
    creds = Credentials.from_authorized_user_info(creds_info)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("drive", "v3", credentials=creds)

# 📤 Google Drive 업로드 함수 (원래 기능 유지: 권한 설정 및 링크 반환 추가)
def upload_to_drive(filename, full_text):
    service = get_drive_service()

    file_metadata = {
        "name": filename,
        "parents": [FOLDER_ID]
    }

    file_stream = io.BytesIO(full_text.encode("utf-8"))
    media = MediaIoBaseUpload(file_stream, mimetype="text/plain", resumable=True)

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()
    
    file_id = file.get("id")

    # 링크 공유 권한 설정
    service.permissions().create(
        fileId=file_id,
        body={'type': 'anyone', 'role': 'reader'}
    ).execute()

    # 링크 가져오기
    file_info = service.files().get(fileId=file_id, fields="webViewLink").execute()
    return file_info.get("webViewLink")

@app.get("/{skey}", response_class=PlainTextResponse) # 반환 타입을 텍스트로 지정
def get_data(skey: str):
    base_url = "https://sd.wips.co.kr/wipslink/doc/docContJson.wips"
    tabs = ["DS", "AB", "CL"]
    headers = {"User-Agent": "Mozilla/5.0"}
    raw = {}

    try:
        for tab in tabs:
            url = f"{base_url}?skey={skey}&tabGb={tab}"
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            raw[tab] = resp.json()

        ab = raw.get("AB", {})
        ds = raw.get("DS", {})
        cl = raw.get("CL", {})

        # 데이터 정리
        title = clean_text(ab.get("docPageSummaryRsltVO", {}).get("invTiList", [{}])[0].get("invTi")) or "제목 없음"
        pub_num = ab.get("docPageSummaryRsltVO", {}).get("mngNum") or "정보 없음"
        appl_num = ab.get("docPageSummaryRsltVO", {}).get("applNum") or "정보 없음"
        abstract = clean_text(ab.get("docPageSummaryRsltVO", {}).get("abList", [{}, {}])[1].get("ab")) or "요약 정보가 없습니다."
        
        claims = [clean_text(c.get("cl")) for c in cl.get("clList", []) if c.get("cl")]
        description = [clean_text(d.get("dtlDesc")) for d in ds.get("descList", []) if d.get("dtlDesc")]

        # 1️⃣ 구글 드라이브에 저장할 텍스트 구성 (기본 형식 유지)
        drive_content = [
            f"제목: {title}",
            f"SKEY: {skey}",
            f"공개번호: {pub_num}",
            f"출원번호: {appl_num}",
            "\n[요약]", abstract,
            "\n[청구항]"
        ]
        for i, c in enumerate(claims, 1): drive_content.append(f"제 {i}항: {c}")
        drive_content.append("\n[상세설명]")
        drive_content.extend(description)
        
        full_text_for_drive = "\n".join(drive_content)
        
        # 2️⃣ 드라이브 업로드 및 링크 생성
        drive_link = upload_to_drive(f"{skey}.txt", full_text_for_drive)

        # 3️⃣ 웹 브라우저에 보여줄 텍스트 구성 (SKEY 바로 다음에 공유 링크 추가)
        web_display_content = [
            f"제목: {title}",
            f"SKEY: {skey}",
            f"공유링크: {drive_link}",  # <--- 웹 화면 출력 시에만 SKEY 밑에 추가
            f"공개번호: {pub_num}",
            f"출원번호: {appl_num}",
            "\n[요약]", abstract,
            "\n[청구항]"
        ]
        for i, c in enumerate(claims, 1): web_display_content.append(f"제 {i}항: {c}")
        web_display_content.append("\n[상세설명]")
        web_display_content.extend(description)

        return "\n".join(web_display_content)

    except Exception as e:
        return f"Error: {str(e)}"
