FROM python:alpine

WORKDIR /app
COPY ./requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY ./main.py ./

EXPOSE 8000
CMD ["uvicorn", "--host", "0.0.0.0", "main:app"]
