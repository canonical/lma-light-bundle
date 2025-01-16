#!/bin/sh

# For all charms in $model_name that have the $expected_relation:$expected_interface, check if they are related to the $expected_related_charm

model_name="$1"
expected_related_charm="$2"
expected_relation="$3"
expected_interface="$4"

for charm in $(juju status -m "$model_name" --format=json | jq -r '.applications | keys[]'); do
  metadata_yaml=$(juju ssh -m "$model_name" ${charm}/0 "cat agents/unit-${charm}-0/charm/metadata.yaml")
  
  # Extract interface information
  interface_requires=$(echo "$metadata_yaml" | yq '.requires | .'$expected_relation'.interface')
  interface_provides=$(echo "$metadata_yaml" | yq '.provides | .'$expected_relation'.interface')

  # Check if interfaces match the expected one
  if [[ "$interface_requires" == "$expected_interface" || "$interface_provides" == "$expected_interface" ]]; then    
    is_charm_related=$(juju status -m "$model_name" --format=json | jq -r '[.applications.'$expected_related_charm'.relations[] | map(select(.["related-application"] == "'$charm'"))] | add | length > 0')
    if [[ "$is_charm_related" == "true" ]]; then
      echo "INFO: $charm is related to $expected_related_charm via interface: $expected_relation:$expected_interface"
    else
      echo "ERROR: $charm is NOT related to $expected_related_charm"
    fi
  else
    echo "INFO: $charm does not have the expected interface: $expected_relation:$expected_interface"
  fi
done

