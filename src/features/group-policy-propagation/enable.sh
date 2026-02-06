#!/bin/bash

dpkg-divert --divert /usr/bin/dpkg.distrib --rename /usr/bin/dpkg
chmod +x /opt/aqua/sys/frameworks/GroupPolicyPropagationFramework/dpkg-wrapper/dpkg.sh
ln -s /opt/aqua/sys/frameworks/GroupPolicyPropagationFramework/dpkg-wrapper/dpkg.sh /usr/bin/dpkg
chmod +x /usr/bin/dpkg
