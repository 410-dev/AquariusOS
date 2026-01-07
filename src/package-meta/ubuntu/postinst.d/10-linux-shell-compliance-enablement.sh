#!/bin/bash

/opt/aquariusos/sys/sbin/reg.sh root install /opt/aquariusos/share/nixshcompliance/registry-template.regtree
#/usr/local/sbin/apprun-prepare.sh /opt/aquariusos/services/me.hysong.services.nixshcompliance.apprun # This is enabled by 5-prepare-bundles.sh
/opt/aquariusos/sys/sbin/services.sh enable me.hysong.services.nixshcompliance
