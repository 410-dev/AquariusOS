#!/bin/bash

# Install all default registries in {{OSCORE}}/templates/registry/

for regtree_file in {{OSCORE}}/templates/registry/*.regtree; do
    {{SYS_CMDS}}/reg.sh root install "$regtree_file"
done
# End of script
