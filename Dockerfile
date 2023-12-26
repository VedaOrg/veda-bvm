FROM python:3.9-slim

RUN apt-get update
RUN apt install python3-dev gcc g++ libleveldb-dev -y

WORKDIR /code
COPY . /code
RUN python setup.py install

RUN mkdir /data && mkdir /rootdir

ENTRYPOINT ["veda", "--veda-root-dir=/rootdir", "--data-dir=/data", "--enable-http-apis=eth,veda", "--internal-rpc-http-listen-address=0.0.0.0"]