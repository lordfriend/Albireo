FROM ubuntu:16.04

# If you have hash mismatch issue, uncomment this line
# RUN rm -rf /var/lib/apt/lists/* && apt clean

RUN apt update && apt install -y wget tar python python-pip curl libcurl4-openssl-dev locales

RUN mkdir -p /usr/app

WORKDIR /usr/app

RUN apt install -y ffmpeg postgresql-client python-dev libyaml-dev python-psycopg2 openssl python-imaging

RUN apt install -y build-essential libssl-dev libffi-dev nodejs

COPY requirements.txt .

RUN pip install -r requirements.txt

RUN locale-gen en_US.UTF-8

ENV LANG en_US.UTF-8

RUN useradd -u 1000 --create-home user

RUN chown user:user -R /usr/app

RUN mkdir -p /data

RUN chown user:user -R /data

USER user

COPY ./ /usr/app/
