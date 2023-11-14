#!/usr/bin/with-contenv bashio

set -eux

echo "Hello, World!"

#(cd hue-thief && python3 -c "import hue_thief; print(hue-thief)")

python3 hue-thief/hue-thief.py "/dev/ttyAMA1" -b 57600
