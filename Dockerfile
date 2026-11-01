FROM python:3.14.6

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p uploads

CMD [ "fastapi", "run", "main.py", "--proxy-headers", "--port", "80" ]


