#!/usr/bin/with-contenv bashio

set -eux

echo "Hello, World!"


CONFIG_PATH=/data/options.json

#echo "Found the following in a config file"
#ls /data
#cat ${CONFIG_PATH}

DEVICE=$(bashio::config 'device')
BAUD_RATE=$(bashio::config 'baud_rate')


#(cd hue-thief && python3 -c "import hue_thief; print(hue-thief)")

#python3 bellows devices

python3 hue-thief/hue-thief.py ${DEVICE} -b ${BAUD_RATE}
