FROM ubuntu:16.04

# --------------------------
# install opencv and python
# --------------------------
RUN apt-get update && \
    apt-get install -y build-essential apt-utils \
    cmake git libgtk2.0-dev pkg-config libavcodec-dev \
    libavformat-dev libswscale-dev

RUN  apt-get update && apt-get install -y python-dev python-numpy \
  python3 python3-pip python3-dev libtbb2 libtbb-dev \
  libjpeg-dev libjasper-dev libdc1394-22-dev \
  python-opencv libopencv-dev libav-tools python-pycurl \
  libatlas-base-dev gfortran webp qt5-default libvtk6-dev zlib1g-dev

RUN pip3 install numpy

RUN cd ~/ &&\
    git clone https://github.com/Itseez/opencv.git &&\
    git clone https://github.com/Itseez/opencv_contrib.git &&\
    cd opencv && mkdir build && cd build && cmake  -DWITH_QT=ON -DWITH_OPENGL=ON -DFORCE_VTK=ON -DWITH_TBB=ON -DWITH_GDAL=ON -DWITH_XINE=ON -DBUILD_EXAMPLES=ON .. && \
    make -j4 && make install && ldconfig && rm -rf ~/opencv*  # Remove the opencv folders to reduce image size

# Set the appropriate link
RUN ln /dev/null /dev/raw1394

# --------------------------
# install java for the amazon-kcl
# --------------------------
ENV JAVA_HOME       /usr/lib/jvm/java-8-oracle
ENV LANG            en_US.UTF-8
ENV LC_ALL          en_US.UTF-8

RUN apt-get update && \
  apt-get install -y --no-install-recommends locales && \
  locale-gen en_US.UTF-8 && \
  apt-get dist-upgrade -y && \
  apt-get --purge remove openjdk* && \
  echo "oracle-java8-installer shared/accepted-oracle-license-v1-1 select true" | debconf-set-selections && \
  echo "deb http://ppa.launchpad.net/webupd8team/java/ubuntu xenial main" > /etc/apt/sources.list.d/webupd8team-java-trusty.list && \
  apt-key adv --keyserver keyserver.ubuntu.com --recv-keys EEA14886 && \
  apt-get update && \
  apt-get install -y --no-install-recommends oracle-java8-installer oracle-java8-set-default && \
  apt-get install -y dos2unix && \
  apt-get clean all

COPY requirements.txt /usr/pose_recognizer/requirements.txt
WORKDIR /usr/pose_recognizer
RUN pip3 install -r requirements.txt
COPY tf-openpose ./tf-openpose
COPY . /usr/pose_recognizer
RUN dos2unix ./start_producer.sh && chmod +x ./start_producer.sh
RUN cd tf-openpose && python3 setup.py install && cd ..
RUN rm -rf tf-openpose

#CMD ["./start_producer"]
CMD ["python3", "-m", "src.server.server_multithreaded"]
# default entry point is /bin/sh
#CMD ["python3", "-m", "src.server.server_multithreaded"]
#`awskcl_helper.py --print_command \
#    --java <path-to-java> --properties samples/sample.properties`
#
#CMD ['python3'awskcl_helper.py']
