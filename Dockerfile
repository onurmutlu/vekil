FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY webapp webapp
RUN useradd --create-home shop && mkdir -p /srv/data && chown shop /srv/data
USER shop
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
