# Usage Workflow

## Installation
1. Install the [Goss binary](https://goss.readthedocs.io/en/stable/installation/).

## Fetch the goss.yaml files
To validate a model, `goss.yaml` files (customised to a specific deployment) are required. These files can be decentralised, but must exist on the FS for Goss validation. For cos-lite-bundle these files exist in [cos-lite-bundle/goss](https://github.com/canonical/cos-lite-bundle/tree/feature/goss-complex/goss).

2. `git clone --branch feature/goss-complex https://github.com/canonical/cos-lite-bundle.git && cd cos-lite-bundle`

## Test with Goss
### Manually
3. `juju add-model cos-model`
4. `juju deploy cos-lite --trust`
5. `juju status --watch 1s` -> wait for `active/idle`
6. `goss -g goss/goss.yaml --vars goss/vars.yaml --vars-inline '{"goss_dir": "goss"}' validate -f documentation`

Sample results:
```
Total Duration: 2.375s
Count: 22, Failed: 0, Skipped: 0
```

### With integration Tests
3. `tox -e render-edge`
4. `tox -e integration`

## Contributing

1. See the docs for [quickstart](https://goss.readthedocs.io/en/stable/quickstart/), [goss-test-creation](https://goss.readthedocs.io/en/stable/gossfile/#goss-test-creation), [gossfile](https://goss.readthedocs.io/en/stable/gossfile/#gossfile), and [complex examples](https://goss.readthedocs.io/en/stable/gossfile/#examples).
2. Modify the contents of the goss directory according to your needs.
3. Ensure all the integration tests pass.
