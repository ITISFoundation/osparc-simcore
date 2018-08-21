#!/bin/bash

sed -i -e '/"--authKey", "${secret}",/a "--proxies", "/home/root/config/visualizer_config.json",' /opt/wslink-launcher/launcher-template.json