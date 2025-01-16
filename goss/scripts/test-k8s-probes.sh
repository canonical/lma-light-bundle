#!/bin/sh

pod_ips=$(kubectl get pods -n cos-model -o jsonpath='{.items[*].status.podIP}' | tr ' ' '\n')

# Loop over each IP address
echo "$pod_ips" | while IFS= read -r ip; do
  
    health=$(curl -sL http://$ip:38812/v1/health | jq -r '.result.healthy')
    if [ "$health" != "true" ]; then
        echo "Curl failed for $ip"
    fi
done