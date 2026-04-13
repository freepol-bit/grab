from fastapi import FastAPI
import requests
import json
import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io

app = FastAPI()

# 👉 구글 드라이브 폴더 ID (본인의 폴더 ID로 유지)
FOLDER_ID = "1Mh3gAlf63tq5_oiKAP4k-d5FAHbA6Z6o"

# 🔐 Google Drive OAuth 2.0 인증 함수
def get_drive_service():
    # Render 환경변수 'GOOGLE_USER_CREDENTIALS'에 저장한 JSON 문자열 로드
    creds_json = os.environ.get("GOOGLE_USER_CREDENTIALS")
    if not creds_json:
        raise Exception("환경변수 GOOGLE_USER_CREDENTIALS를 찾을 수 없습니다.")
    
    creds_info = json.loads(creds_json)
    creds = Credentials.from_authorized_user_info(creds_info)

    # 🔄 토큰이 만료되었다면 refresh_token을 사용하여 자동 갱신
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

    # 데이터를 JSON 바이너리로 변환
    file_stream = io.BytesIO(
        json.dumps(data, ensure_ascii=False).encode("utf-8")
    )

    media = MediaIoBaseUpload(file_stream, mimetype="application/json")

    # 파일 생성 실행
    service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()

@app.get("/")
def root():
    return {"message": "FastAPI + Google Drive OAuth2 API Running"}

@app.get("/{skey}")
def get_data(skey: str):
    base_url = "https://sd.wips.co.kr/wipslink/doc/docContJson.wips"
    tabs = ["DS", "AB", "CL"]
    headers = {"User-Agent": "Mozilla/5.0"}
    raw = {}

    try:
        # 1️⃣ 데이터 크롤링
        for tab in tabs:
            url = f"{base_url}?skey={skey}&tabGb={tab}"
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            raw[tab] = resp.json()

        # 2️⃣ 데이터 정제 로직
        ab = raw.get("AB", {})
        ds = raw.get("DS", {})
        cl = raw.get("CL", {})

        result = {
            "SKEY": skey,
            "Pubnum": ab.get("docPageSummaryRsltVO", {}).get("mngNum"),
            "Applnum": ab.get("docPageSummaryRsltVO", {}).get("applNum"),
            "title": None,
            "image": ds.get("docPageDescriptionRsltVO", {}).get("exmpDrwImg"),
            "abstract": None,
            "claims": [],
            "description": []
        }

        # 제목 추출 안전하게 처리
        try:
            inv_ti_list = ab.get("docPageSummaryRsltVO", {}).get("invTiList", [])
            if inv_ti_list:
                result["title"] = inv_ti_list[0].get("invTi")
        except: pass

        # 요약 추출 안전하게 처리
        try:
            ab_list = ab.get("docPageSummaryRsltVO", {}).get("abList", [])
            if len(ab_list) > 1:
                result["abstract"] = ab_list[1].get("ab")
        except: pass

        # 청구항 및 상세설명 리스트 처리
        result["claims"] = [c.get("cl") for c in cl.get("clList", []) if "cl" in c]
        result["description"] = [d.get("dtlDesc") for d in ds.get("descList", []) if "dtlDesc" in d]

        # 3️⃣ Google Drive 저장 (본인 계정 용량 사용)
        filename = f"{skey}.txt"
        upload_to_drive(filename, result)

        return {
            "status": "success",
            "file_uploaded": filename,
            "data": result
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
