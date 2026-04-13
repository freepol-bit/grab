from fastapi import FastAPI
import requests

app = FastAPI()

@app.get("/{skey}")
def get_data(skey: str):
    url = f"https://sd.wips.co.kr/wipslink/doc/docContJson.wips?skey={skey}&tabGb=DS"
    
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()  # JSON 그대로 반환

    except Exception as e:
        return {"error": str(e)}
