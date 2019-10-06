FROM python:3

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /usr/src/app

RUN python ./manage.py migrate && \
    python ./manage.py loaddata ctrack/fixtures/*.yaml
EXPOSE 8000
CMD [ "python", "./manage.py", "runserver", "0.0.0.0:8000"]
