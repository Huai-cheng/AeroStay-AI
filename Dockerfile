FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml ./
COPY pipeline ./pipeline
COPY etl ./etl
COPY prototype ./prototype
COPY .streamlit ./.streamlit
RUN pip install --no-cache-dir --timeout 120 .

EXPOSE 8000 8501
CMD ["uvicorn", "prototype.api:app", "--host", "0.0.0.0", "--port", "8000"]
