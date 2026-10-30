#!/bin/bash
# Uzycie: sudo ./stop.sh <interfejs>  - zdejmuje dodatkowe adresy IP
IF="${1:?podaj interfejs}"
ifconfig "$IF" inet 192.168.1.1 -alias 2>/dev/null
ifconfig "$IF" inet 192.168.254.254 -alias 2>/dev/null
ifconfig "$IF" | grep inet || echo "brak adresow IPv4 na $IF"
