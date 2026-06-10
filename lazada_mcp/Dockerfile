FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Chromium is already installed in the base image — no extra install needed

COPY . .

EXPOSE 7771

CMD ["python", "server.py", "--sse", "--port", "7771"]
