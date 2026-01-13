#!/bin/bash

/opt/aqua/sys/sbin/reg.sh root install /opt/aqua/share/nixshcompliance/registry-template.regtree
#/usr/local/sbin/apprun-prepare.sh /opt/aqua/services/me.hysong.services.nixshcompliance.apprun # This is enabled by 5-prepare-bundles.sh
/opt/aqua/sys/sbin/services.sh enable me.hysong.services.nixshcompliance
