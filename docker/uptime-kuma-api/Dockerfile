FROM python:alpine

WORKDIR /app
COPY ./requirements.txt ./

RUN pip install -r requirements.txt 

COPY ./main.py ./

EXPOSE 8000
CMD ["uvicorn", "--host", "0.0.0.0", "main:app"]
