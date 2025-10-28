FROM alpine:3.18

WORKDIR /app

RUN apk add --no-cache \
        python3 \
        py3-pip \
        ca-certificates
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python3", "main.py"]
