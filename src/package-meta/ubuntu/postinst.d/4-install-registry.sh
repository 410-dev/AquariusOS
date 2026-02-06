#!/bin/bash

# Install all default registries in /opt/aqua/sys/registry/

for regtree_file in /opt/aqua/sys/registry/*.regtree; do
    /opt/aqua/sys/sbin/reg.sh root install "$regtree_file"
done
# End of script
