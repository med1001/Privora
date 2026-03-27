import os
import shutil
import uuid

filepath = r'C:\Users\homepc\Desktop\privora_project\Privora\server\src\main.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

import re

if 'StaticFiles' not in content:
    content = content.replace('from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Header, HTTPException, Query\n', 'from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Header, HTTPException, Query, File, UploadFile\nfrom fastapi.staticfiles import StaticFiles\nimport uuid, shutil, os\n')

if 'app.mount' not in content:
    content = content.replace('app = FastAPI()', 'app = FastAPI()\n\nos.makedirs("uploads", exist_ok=True)\napp.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")')

upload_endpoint = '''
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    # 10 MB limit check can be done by validating file size, but UploadFile handles streaming gracefully.
    try:
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4().hex}{file_extension}"
        file_path = os.path.join("uploads", unique_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        file_size = os.path.getsize(file_path)
        if file_size > 10 * 1024 * 1024:
            os.remove(file_path)
            return {"error": "File too large. Maximum size is 10MB."}

        return {"url": f"/uploads/{unique_filename}", "filename": file.filename, "type": file.content_type}
    except Exception as e:
        return {"error": str(e)}
'''

if '/api/upload' not in content:
    content = content + '\n' + upload_endpoint

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated main.py")
