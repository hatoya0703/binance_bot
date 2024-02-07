FROM python:3.11.7-slim-bullseye

WORKDIR /user/src/app

COPY requirements.txt ./
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "python", "./btc.py" ]