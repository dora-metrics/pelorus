FROM python:3.7.4

RUN pip install --upgrade pip
RUN pip install pylama

COPY entrypoint.sh /
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
