FROM python:alpine

ENV TZ=Europe/London

WORKDIR /app
COPY ./requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY ./k8s-pod-resolver.py ./

CMD ["python", "k8s-pod-resolver.py"]
