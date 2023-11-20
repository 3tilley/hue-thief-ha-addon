#!/usr/bin/with-contenv bashio

set -eu

echo "Running hue-thief-ha-addon version ${BUILD_VERSION:-local-dev}"


# CONFIG_PATH=/data/options.json

#echo "Found the following in a config file"
#ls /data
#cat ${CONFIG_PATH}

DEVICE=$(bashio::config 'device' "${ENV_DEVICE:-null}")
BAUD_RATE=$(bashio::config 'baud_rate' "${ENV_BAUD_RATE:-null}")
RUN_MAIN=$(bashio::config 'run_main' "${ENV_RUN_MAIN:server}")

echo "Testing write permissions"
test -w ${DEVICE} && echo success || echo failure 

test -w ${DEVICE} && success=true || success=false

echo "Testing permissions for $(whoami)"
if [[ $success == "false" ]] && [[ "${ENV_CHECK_DEVICE:-1}" != "0" ]]; then
    sudo chown $(whoami) ${DEVICE}
fi
#(cd hue-thief && python3 -c "import hue_thief; print(hue-thief)")

#python3 bellows devices

#python3 litestar-server.py ${DEVICE} -b ${BAUD_RATE}
if [[ $RUN_MAIN == "server" ]]; then
    echo "Running server"
    python3 litestar-server.py ${DEVICE} -b ${BAUD_RATE}
elif [[ $RUN_MAIN == "old-script" ]]; then
    echo "Running original hue-thief script"
    python3 old-hue-thief.py ${DEVICE} -b ${BAUD_RATE}
else
    echo "Running new version of script"
    python3 hue_thief.py ${DEVICE} -b ${BAUD_RATE} --no-reset
fi

