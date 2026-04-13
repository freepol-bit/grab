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

# 👉 구글 드라이브 폴더 ID
FOLDER_ID = "1Mh3gAlf63tq5_oiKAP4k-d5FAHbA6Z6o"

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

# 📤 Google Drive 업로드 함수 (NotebookLM 최적화 버전)
def upload_to_drive(filename, data):
    service = get_drive_service()

    file_metadata = {
        "name": filename,
        "parents": [FOLDER_ID],
        "mimeType": "text/plain"  # 드라이브 상의 파일 타입 명시
    }

    # 1️⃣ NotebookLM이 읽기 좋게 "문서 형태"로 텍스트 구성
    content_parts = []
    content_parts.append(f"제목: {data.get('title') or '제목 없음'}")
    content_parts.append(f"SKEY: {data.get('SKEY')}")
    content_parts.append(f"공개번호: {data.get('Pubnum') or '정보 없음'}")
    content_parts.append(f"출원번호: {data.get('Applnum') or '정보 없음'}")
    content_parts.append("\n[요약]\n" + (data.get('abstract') or "요약 정보가 없습니다."))
    
    content_parts.append("\n[청구항]")
    claims = data.get('claims', [])
    if claims:
        for i, claim in enumerate(claims, 1):
            content_parts.append(f"제 {i}항: {claim}")
    else:
        content_parts.append("청구항 정보가 없습니다.")

    content_parts.append("\n[상세설명]")
    description = data.get('description', [])
    if description:
        content_parts.extend(description)
    else:
        content_parts.append("상세설명 정보가 없습니다.")

    # 전체 리스트를 하나의 문자열로 합침
    full_text = "\n".join(content_parts)

    # 2️⃣ UTF-8 인코딩으로 바이너리 스트림 생성
    file_stream = io.BytesIO(full_text.encode("utf-8"))

    # 3️⃣ 미디어 업로드 설정 (mimetype 중요)
    media = MediaIoBaseUpload(file_stream, mimetype="text/plain", resumable=True)

    # 4️⃣ 파일 생성 실행
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
            "abstract": None,
            "claims": [],
            "description": []
        }

        # 제목 추출
        try:
            inv_ti_list = ab.get("docPageSummaryRsltVO", {}).get("invTiList", [])
            if inv_ti_list:
                result["title"] = inv_ti_list[0].get("invTi")
        except: pass

        # 요약 추출
        try:
            ab_list = ab.get("docPageSummaryRsltVO", {}).get("abList", [])
            if len(ab_list) > 1:
                result["abstract"] = ab_list[1].get("ab")
        except: pass

        # 청구항 및 상세설명 처리
        result["claims"] = [c.get("cl") for c in cl.get("clList", []) if c.get("cl")]
        result["description"] = [d.get("dtlDesc") for d in ds.get("descList", []) if d.get("dtlDesc")]

        # 3️⃣ Google Drive 저장 (확장자 .txt 및 텍스트 포맷팅 적용)
        filename = f"{skey}.txt"
        upload_to_drive(filename, result)

        return {
            "status": "success",
            "file_uploaded": filename,
            "data_summary": {
                "title": result["title"],
                "claims_count": len(result["claims"])
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
