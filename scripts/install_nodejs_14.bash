#
# Install Node.js 14 on Ubuntu
#
# Requirements for development machines
#
#
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'

sudo apt update

# Script to install the NodeSource Node.js 14.x repo onto a Debian or Ubuntu system
curl -sL https://deb.nodesource.com/setup_14.x | sudo bash -

# Verify new source
cat /etc/apt/sources.list.d/nodesource.list

# Installs node-js
apt-get install -y nodejs
