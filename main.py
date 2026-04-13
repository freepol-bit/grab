from fastapi import FastAPI
import requests
import json
import os
import re  # 정규식 라이브러리 추가
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io

app = FastAPI()

# 👉 구글 드라이브 폴더 ID
FOLDER_ID = "1Mh3gAlf63tq5_oiKAP4k-d5FAHbA6Z6o"

# ✨ 텍스트 정제 함수 (HTML 태그 및 특수 메타데이터 제거)
def clean_text(raw_html):
    if not raw_html:
        return ""
    # 1. <...> 형태의 모든 HTML/XML 태그 제거
    clean = re.sub(r'<[^>]*>', ' ', raw_html)
    # 2. <?...?> 형태의 XML 선언문 제거
    clean = re.sub(r'\?.*?\?', '', clean)
    # 3. 연속된 공백 및 줄바꿈 정리
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

# 🔐 Google Drive OAuth 2.0 인증 함수
def get_drive_service():
    creds_json = os.environ.get("GOOGLE_USER_CREDENTIALS")
    if not creds_json:
        raise Exception("환경변수 GOOGLE_USER_CREDENTIALS를 찾을 수 없습니다.")
    
    creds_info = json.loads(creds_json)
    creds = Credentials.from_authorized_user_info(creds_info)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    
    return build("drive", "v3", credentials=creds)

# 📤 Google Drive 업로드 함수
def upload_to_drive(filename, data):
    service = get_drive_service()

    file_metadata = {
        "name": filename,
        "parents": [FOLDER_ID]
    }

    # 1️⃣ 모든 항목에 대해 clean_text 적용하여 텍스트 구성
    content_parts = []
    content_parts.append(f"제목: {clean_text(data.get('title')) or '제목 없음'}")
    content_parts.append(f"SKEY: {data.get('SKEY')}")
    content_parts.append(f"공개번호: {data.get('Pubnum') or '정보 없음'}")
    content_parts.append(f"출원번호: {data.get('Applnum') or '정보 없음'}")
    
    content_parts.append("\n[요약]")
    content_parts.append(clean_text(data.get('abstract')) or "요약 정보가 없습니다.")
    
    content_parts.append("\n[청구항]")
    claims = data.get('claims', [])
    if claims:
        for i, claim in enumerate(claims, 1):
            # 청구항 내부의 태그도 모두 제거
            content_parts.append(f"제 {i}항: {clean_text(claim)}")
    else:
        content_parts.append("청구항 정보가 없습니다.")

    content_parts.append("\n[상세설명]")
    description = data.get('description', [])
    if description:
        # 리스트 내의 각 문장을 정제하여 합침
        full_desc = "\n".join([clean_text(d) for d in description if d])
        content_parts.append(full_desc)
    else:
        content_parts.append("상세설명 정보가 없습니다.")

    # 전체 리스트를 하나의 문자열로 합침
    full_text = "\n".join(content_parts)

    # 2️⃣ 바이너리 변환 및 업로드
    file_stream = io.BytesIO(full_text.encode("utf-8"))
    media = MediaIoBaseUpload(file_stream, mimetype="text/plain", resumable=True)

    service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()

@app.get("/")
def root():
    return {"message": "FastAPI + Google Drive Clean Text API Running"}

@app.get("/{skey}")
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

        result = {
            "SKEY": skey,
            "Pubnum": ab.get("docPageSummaryRsltVO", {}).get("mngNum"),
            "Applnum": ab.get("docPageSummaryRsltVO", {}).get("applNum"),
            "title": None,
            "abstract": None,
            "claims": [],
            "description": []
        }

        # 데이터 추출 (정제 전 원본 데이터 수집)
        try:
            inv_ti_list = ab.get("docPageSummaryRsltVO", {}).get("invTiList", [])
            if inv_ti_list: result["title"] = inv_ti_list[0].get("invTi")
        except: pass

        try:
            ab_list = ab.get("docPageSummaryRsltVO", {}).get("abList", [])
            if len(ab_list) > 1: result["abstract"] = ab_list[1].get("ab")
        except: pass

        result["claims"] = [c.get("cl") for c in cl.get("clList", []) if c.get("cl")]
        result["description"] = [d.get("dtlDesc") for d in ds.get("descList", []) if d.get("dtlDesc")]

        # 3️⃣ Google Drive 저장 (clean_text 로직 포함됨)
        filename = f"{skey}.txt"
        upload_to_drive(filename, result)

        return {
            "status": "success",
            "file_uploaded": filename
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
