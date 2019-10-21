FROM ubuntu:18.10

RUN apt-get update && apt-get install -y python3-pip gdal-bin python3-gdal
RUN apt-get install wget

ADD requirements.txt /tmp/
RUN pip3 install -r /tmp/requirements.txt

RUN mkdir -p /opt/alos

WORKDIR /opt/alos

ADD alos_process.py run_job.py get_uuid.py /opt/alos/

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

CMD /opt/alos/run_job.py
