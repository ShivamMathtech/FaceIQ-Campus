FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
COPY scripts scripts
COPY model-manifest.json model-manifest.json
RUN useradd --create-home faceiq && mkdir -p storage/models && chown -R faceiq:faceiq /app
USER faceiq
EXPOSE 8000
CMD ["python","-m","uvicorn","app.main:app","--app-dir","backend","--host","0.0.0.0","--port","8000","--workers","1","--ws-max-size","65536"]
