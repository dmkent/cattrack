FROM python:3.7

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN mkdir /code
WORKDIR /code
COPY requirements.txt /code/
RUN pip install --no-cache-dir -r requirements.txt

COPY ./ /code/

EXPOSE 8000
RUN python ./manage.py migrate && \
    python ./manage.py loaddata ctrack/fixtures/*.yaml
CMD [ "python", "./manage.py", "runserver", "0.0.0.0:8000"]