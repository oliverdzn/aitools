FROM mcr.microsoft.com/playwright/python:v1.60.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7772

CMD ["python", "server.py", "--sse", "--port", "7772"]
