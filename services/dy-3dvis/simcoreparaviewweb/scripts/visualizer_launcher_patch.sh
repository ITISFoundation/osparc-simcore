#!/bin/bash

sed -i -e '/"--authKey", "${secret}",/a "--settings-lod-threshold", "5",' /opt/wslink-launcher/launcher-template.json