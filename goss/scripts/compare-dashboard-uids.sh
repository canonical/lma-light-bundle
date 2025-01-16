#!/bin/bash

# Collect the UID from the charm dashboard and check if it is a subset of Grafana dashboard UIDs

model_name="$1"
grafana_app="$2"
other_app="$3"
grafana_dashboard_dir="/etc/${grafana_app}/provisioning/dashboards/"
other_app_dashboard_dir="agents/unit-${other_app}-0/charm/src/grafana_dashboards/"
target_uid=$(juju ssh ${other_app}/0 "cat ${other_app_dashboard_dir}/${other_app}*.json.tmpl" | jq -r '.uid')

# Get the list of JSON files in the Grafana dashboard directory inside the workload container
files=$(juju ssh --container grafana grafana/0 "find $grafana_dashboard_dir -type f -name '*.json'")
match_found=false

# Iterate over each dashboard file
for file_path in ${files}; do
  uid=$(juju ssh --container grafana grafana/0 "cat ${file_path}" | jq -r '.uid')
  if [ "$uid" == "$target_uid" ]; then
    match_found=true
    break  # Exit the loop early since a match was found
  fi
done

if [ "$match_found" = true ]; then
  echo -n "Match found."
else
  echo -n "The ${other_app} dashboard UID is not a subset of the Grafana dashboard UIDs."
fi
