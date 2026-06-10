from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import httpx
import os

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SUPABASE_URL = "https://qtrniovpkrwimeohamkc.supabase.co"
SUPABASE_KEY = "sb_publishable_XwiSTQrkI0d1Wfj2nLqdLg_qPn48OEu"
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}

@app.get("/api/data/{user_id}")
async def get_data(user_id: str):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{SUPABASE_URL}/rest/v1/uma_data?id=eq.{user_id}", headers=HEADERS)
        rows = r.json()
        if rows and rows[0].get("data"):
            return JSONResponse(rows[0]["data"])
        return JSONResponse({})

@app.post("/api/data/{user_id}")
async def save_data(user_id: str, request: Request):
    body = await request.json()
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{SUPABASE_URL}/rest/v1/uma_data", headers={**HEADERS, "Prefer": "resolution=merge-duplicates,return=minimal"}, json={"id": user_id, "data": body})
        if r.status_code not in (200, 201, 204):
            raise HTTPException(status_code=500, detail=r.text)
        return JSONResponse({"ok": True})

@app.get("/{full_path:path}")
async def frontend(full_path: str):
    return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
