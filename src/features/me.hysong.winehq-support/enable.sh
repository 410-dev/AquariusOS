#!/bin/bash

mkdir -pm755 /etc/apt/keyrings
dpkg --add-architecture i386
wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/noble/winehq-noble.sources
wget -O - https://dl.winehq.org/wine-builds/winehq.key | sudo gpg --dearmor -o /etc/apt/keyrings/winehq-archive.key -
apt install winehq-stable winehq-stable-i386 wine-stable-amd64 wine-stable-i386 -y