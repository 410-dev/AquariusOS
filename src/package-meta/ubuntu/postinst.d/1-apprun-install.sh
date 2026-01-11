#!/bin/bash

set -e

ln -s /usr/local/sbin/apprun.sh /usr/local/bin/apprun
ln -s /usr/local/sbin/apprunutil.sh /usr/local/bin/apprunutil
ln -s /usr/local/sbin/appid.sh /usr/local/bin/appid
ln -s /usr/local/sbin/apprun-prepare.sh /usr/local/bin/apprun-prepare
ln -s /usr/local/sbin/dictionary.py /usr/local/bin/dictionary

/usr/local/sbin/apprun-prepare.sh "/opt/aqua/services/me.hysong.aqua.services.apprundropin.apprun"
/opt/aqya/sys/sbin/services.sh enable me.hysong.aqua.services.apprundropin
