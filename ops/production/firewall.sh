#!/bin/sh
# Shared-host ingress policy. Only owns HT_* chains/jumps; never flushes Docker rules.
set -eu

external_interface=ens3
action=${1:-}

remove_owned() {
  command=$1
  input_chain=HT_HOST_INPUT
  docker_chain=HT_DOCKER_INGRESS
  if "$command" -C INPUT -i "$external_interface" -j "$input_chain" 2>/dev/null; then
    "$command" -D INPUT -i "$external_interface" -j "$input_chain"
  fi
  if "$command" -C DOCKER-USER -i "$external_interface" -j "$docker_chain" 2>/dev/null; then
    "$command" -D DOCKER-USER -i "$external_interface" -j "$docker_chain"
  fi
  if "$command" -S "$input_chain" >/dev/null 2>&1; then
    "$command" -F "$input_chain"
    "$command" -X "$input_chain"
  fi
  if "$command" -S "$docker_chain" >/dev/null 2>&1; then
    "$command" -F "$docker_chain"
    "$command" -X "$docker_chain"
  fi
}

apply_family() {
  command=$1
  icmp_protocol=$2
  "$command" -S DOCKER-USER >/dev/null
  # Refuse an unexpected pre-existing chain rather than taking ownership of it.
  if "$command" -S HT_HOST_INPUT >/dev/null 2>&1 || "$command" -S HT_DOCKER_INGRESS >/dev/null 2>&1; then
    echo 'Husky firewall chain already exists; refusing to replace it' >&2
    exit 1
  fi
  "$command" -N HT_HOST_INPUT
  "$command" -A HT_HOST_INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
  "$command" -A HT_HOST_INPUT -p tcp -m multiport --dports 22,80,443 -j RETURN
  "$command" -A HT_HOST_INPUT -p udp --dport 40970 -j RETURN
  "$command" -A HT_HOST_INPUT -p "$icmp_protocol" -j RETURN
  "$command" -A HT_HOST_INPUT -j DROP

  "$command" -N HT_DOCKER_INGRESS
  "$command" -A HT_DOCKER_INGRESS -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
  "$command" -A HT_DOCKER_INGRESS -p tcp -m conntrack --ctdir ORIGINAL --ctorigdstport 80 -j RETURN
  "$command" -A HT_DOCKER_INGRESS -p tcp -m conntrack --ctdir ORIGINAL --ctorigdstport 443 -j RETURN
  "$command" -A HT_DOCKER_INGRESS -p udp -m conntrack --ctdir ORIGINAL --ctorigdstport 40970 -j RETURN
  "$command" -A HT_DOCKER_INGRESS -p "$icmp_protocol" -j RETURN
  "$command" -A HT_DOCKER_INGRESS -j DROP

  "$command" -I INPUT 1 -i "$external_interface" -j HT_HOST_INPUT
  "$command" -I DOCKER-USER 1 -i "$external_interface" -j HT_DOCKER_INGRESS
}

case "$action" in
  apply)
    ip link show "$external_interface" >/dev/null
    # A failed partial installation is recoverable with the separate rollback action.
    apply_family iptables icmp
    apply_family ip6tables ipv6-icmp
    ;;
  rollback)
    remove_owned ip6tables
    remove_owned iptables
    ;;
  *)
    echo 'Usage: firewall.sh apply|rollback' >&2
    exit 2
    ;;
esac
