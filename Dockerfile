FROM python:3.14-alpine
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY /backend/app backend/
EXPOSE 8080
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]