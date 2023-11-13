#!/usr/bin/with-contenv bashio

set -eux

echo "Hello, World!"

python3 -c "import bellows; print(bellows)"
