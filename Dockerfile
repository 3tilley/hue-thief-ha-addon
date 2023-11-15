ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip

# RUN git clone https://github.com/vanviegen/hue-thief
COPY requirements.txt /

RUN pip3 install wheel
RUN pip3 install -r requirements.txt
# for runtime flexibility let's not hard-bake the command into the image
#CMD [ "python3", "hue-thief/hue-thief.py", "/dev/ttyUSB1" ]

COPY run.sh /
RUN mkdir /hue-thief
COPY hue-thief.py /hue-thief/.
COPY interpanZll.py /hue-thief/.
COPY litestar-server.py /hue-thief/.
COPY index.html /hue-thief/.

RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
