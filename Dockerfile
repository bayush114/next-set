FROM node:22-slim AS ui
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY frontend frontend
COPY index.html tsconfig.json ./
RUN npm run build
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend backend
COPY --from=ui /app/dist dist
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
