#Use the Python 3.12 slim base image to match your local environment

FROM python:3.12-slim

#Set the working directory in the container

WORKDIR /app

#Copy the requirements file into the container

COPY requirements.txt /app/

#Install any needed packages specified in requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

#Copy the entire 'app' directory, requirements, and main.py from the repository root into the container's /app directory.

#Since the Dockerfile is in the root, this copies the 'app' folder.

COPY . /app/


EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
