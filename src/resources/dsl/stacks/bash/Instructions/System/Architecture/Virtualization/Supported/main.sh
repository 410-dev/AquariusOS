result="$(lscpu | grep Virtualization)"
if [[ -z "$result" ]]; then
    echo "0"
    exit 1
fi
echo "1"
exit 0
