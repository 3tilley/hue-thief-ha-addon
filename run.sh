#!/usr/bin/with-contenv bashio

set -eux

echo "Hello, World!"

python3 -c "import hue_thief; print(hue-thief)"

python3 hue-thief "/dev/ttyAMA1" -b 57600
