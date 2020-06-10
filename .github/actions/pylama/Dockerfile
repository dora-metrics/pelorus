FROM python:3.7.4

LABEL "com.github.actions.name"="GitHub Action for Pylama"
LABEL "com.github.actions.description"="Run pylama commands on python slim image"
LABEL "com.github.actions.icon"="code"
LABEL "com.github.actions.color"="black"


RUN pip install --upgrade pip
RUN pip install pylama


COPY entrypoint.sh /
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
