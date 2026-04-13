from fastapi import FastAPI
import requests

app = FastAPI()

@app.get("/{skey}")
def get_data(skey: str):
    base_url = "https://sd.wips.co.kr/wipslink/doc/docContJson.wips"
    tabs = ["DS", "AB", "CL"]

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    raw = {}

    try:
        # 1️⃣ 데이터 수집
        for tab in tabs:
            url = f"{base_url}?skey={skey}&tabGb={tab}"
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            raw[tab] = resp.json()

        # 2️⃣ 필요한 값만 추출
        result = {}

        # SKEY
        result["SKEY"] = skey

        # Pubnum / Applnum
        ab = raw.get("AB", {})
        result["Pubnum"] = ab.get("docPageSummaryRsltVO", {}).get("mngNum")
        result["Applnum"] = ab.get("docPageSummaryRsltVO", {}).get("applNum")

        # title
        try:
            result["title"] = ab["docPageSummaryRsltVO"]["invTiList"][0]["invTi"]
        except:
            result["title"] = None

        # image
        ds = raw.get("DS", {})
        result["image"] = ds.get("docPageDescriptionRsltVO", {}).get("exmpDrwImg")

        # abstract
        try:
            result["abstract"] = ab["docPageSummaryRsltVO"]["abList"][1]["ab"]
        except:
            result["abstract"] = None

        # claims (전체 리스트)
        cl = raw.get("CL", {})
        claims_list = cl.get("clList", [])
        result["claims"] = [c.get("cl") for c in claims_list if "cl" in c]

        # description
        desc_list = ds.get("descList", [])
        result["description"] = [d.get("dtlDesc") for d in desc_list if "dtlDesc" in d]

        return result

    except Exception as e:
        return {"error": str(e)}
