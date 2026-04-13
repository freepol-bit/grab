from fastapi import FastAPI

app = FastAPI()

@app.get("/{skey}")
def read_skey(skey: str):
    return {"message": f"Hello {skey}"}
