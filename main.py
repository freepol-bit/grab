from fastapi import FastAPI
import requests
import json
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io

app = FastAPI()

# 👉 네 Google Drive 폴더 ID
FOLDER_ID = "1Mh3gAlf63tq5_oiKAP4k-d5FAHbA6Z6o"


# 🔐 Google Drive 인증 (환경변수 사용)
def get_drive_service():
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])

    creds = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/drive"]
    )

    return build("drive", "v3", credentials=creds)


# 📤 Google Drive 업로드
def upload_to_drive(filename, data):
    service = get_drive_service()

    file_metadata = {
        "name": filename,
        "parents": [FOLDER_ID]
    }

    file_stream = io.BytesIO(
        json.dumps(data, ensure_ascii=False).encode("utf-8")
    )

    media = MediaIoBaseUpload(file_stream, mimetype="application/json")

    service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()


@app.get("/")
def root():
    return {"message": "FastAPI + Google Drive OK"}


@app.get("/{skey}")
def get_data(skey: str):
    base_url = "https://sd.wips.co.kr/wipslink/doc/docContJson.wips"
    tabs = ["DS", "AB", "CL"]

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    raw = {}

    try:
        # 1️⃣ 크롤링
        for tab in tabs:
            url = f"{base_url}?skey={skey}&tabGb={tab}"
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            raw[tab] = resp.json()

        # 2️⃣ 데이터 정제
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

        # title
        try:
            result["title"] = ab["docPageSummaryRsltVO"]["invTiList"][0]["invTi"]
        except:
            pass

        # abstract
        try:
            result["abstract"] = ab["docPageSummaryRsltVO"]["abList"][1]["ab"]
        except:
            pass

        # claims
        result["claims"] = [
            c.get("cl") for c in cl.get("clList", []) if "cl" in c
        ]

        # description
        result["description"] = [
            d.get("dtlDesc") for d in ds.get("descList", []) if "dtlDesc" in d
        ]

        # 3️⃣ Google Drive 저장
        filename = f"{skey}.json"
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
