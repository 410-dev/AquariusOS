#!/bin/bash

dpkg-divert --divert /usr/bin/dpkg.distrib --rename /usr/bin/dpkg
chmod +x {{SYS_FRAMEWORKS}}/GroupPolicyPropagationFramework/dpkg-wrapper/dpkg.sh
ln -s {{SYS_FRAMEWORKS}}/GroupPolicyPropagationFramework/dpkg-wrapper/dpkg.sh /usr/bin/dpkg
chmod +x /usr/bin/dpkg
