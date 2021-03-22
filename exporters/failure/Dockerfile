FROM registry.access.redhat.com/ubi8/python-38

WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
COPY . .

CMD ["python3", "failure/app.py"]
