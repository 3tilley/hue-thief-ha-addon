ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip

# RUN git clone https://github.com/vanviegen/hue-thief
COPY requirements.txt /

RUN pip3 install wheel
RUN pip3 install -r requirements.txt
# for runtime flexibility let's not hard-bake the command into the image
#CMD [ "python3", "hue-thief/hue-thief.py", "/dev/ttyUSB1" ]

RUN mkdir /hue-thief
COPY interpanZll.py /hue-thief/.
COPY litestar-server.py /hue-thief/.
COPY templates/* /hue-thief/templates/
COPY run.sh /hue-thief/.
COPY hue_thief.py /hue-thief/.
COPY old-hue-thief.py /hue-thief/.

RUN chmod a+x hue-thief/run.sh
WORKDIR /hue-thief

CMD [ "./run.sh" ]
