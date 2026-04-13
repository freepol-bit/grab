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

    result = {}

    try:
        for tab in tabs:
            url = f"{base_url}?skey={skey}&tabGb={tab}"
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()

            result[tab] = resp.json()

        return result

    except Exception as e:
        return {"error": str(e)}
