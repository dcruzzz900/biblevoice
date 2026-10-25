FROM python:3.11-slim
WORKDIR /app
ARG LIGHT=0
COPY requirements.txt requirements-light.txt ./
RUN if [ "$LIGHT" = "1" ]; then pip install --no-cache-dir -r requirements-light.txt; else pip install --no-cache-dir -r requirements.txt; fi
COPY . .
ENV DATA_DIR=/data LIGHT=$LIGHT
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request as u;u.urlopen('http://localhost:8000/api/versions')" || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
