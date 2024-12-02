#!/bin/sh

# Obtain the alertmanager_url from Loki's loki-local-config.yaml and test routability from Loki's charm container

model_name="$1"
loki_app="$2"

alertmanager_url=$(juju ssh -m $model_name --container loki ${loki_app}/0 cat /etc/loki/loki-local-config.yaml | yq -r '.ruler.alertmanager_url')
status_code=$(juju ssh -m $model_name ${loki_app}/0 "python3 -c \"import urllib.request; response = urllib.request.urlopen('${alertmanager_url}'); print(response.getcode())\"")

echo -n "Status code: $status_code"