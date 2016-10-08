FROM python:3-onbuild
RUN python ./manage.py migrate && \
    python ./manage.py loaddata ctrack/fixtures/*.yaml
EXPOSE 8000
CMD [ "python", "./manage.py", "runserver", "0.0.0.0:8000"]
