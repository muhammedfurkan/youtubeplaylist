FROM ubuntu:latest
ENV TZ=Europe/Istanbul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN apt-get -y update
RUN apt-get install python3 git python3-pip -y
RUN apt-get update \
    && apt-get -y install libpq-dev \
    gcc \
    git \
    unzip zip \
    wget \
    ffmpeg \
    build-essential coreutils jq pv \
    apt-transport-https \
    && pip install psycopg2
RUN pip3 install -U psycopg2-binary
COPY . .

RUN git clone https://github.com/muhammedfurkan/youtubeplaylist/
RUN cd youtubeplaylist
WORKDIR /youtubeplaylist
RUN pip3 install --no-cache-dir -r requirements.txt

# install requirements
# RUN pip3 install --no-cache-dir -r requirements.txt

# specifies what command to run within the container.
CMD ["python3", "bot.py"]
