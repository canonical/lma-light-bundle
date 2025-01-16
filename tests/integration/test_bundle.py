#!/usr/bin/env python3

# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import json
import logging
import ssl
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.request import urlopen

import juju
import juju.utils
import pytest
import sh
from helpers import (
    ModelConfigChange,
    cli_deploy_bundle,
    get_address,
    get_alertmanager_alerts,
    get_alertmanager_groups,
    get_proxied_url,
)
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)
juju_topology_keys = {"juju_model_uuid", "juju_model", "juju_application"}


# We have a module-scoped parametrization for TLS enablement, so we need to have appropriate
# SSL contexts. This dict is in module scope so that it is visible to all test methods.
# This is needed because the cert's contents is known only after deployment.
@dataclass
class CertContext:
    external_ca: Optional[ssl.SSLContext]


context = CertContext(external_ca=None)

# We also need an insecure context to connect to e.g. unit ip addresses directly
insecure_context = ssl.create_default_context()
insecure_context.check_hostname = False
insecure_context.verify_mode = ssl.CERT_NONE


@pytest.mark.abort_on_fail
@pytest.mark.parametrize("tls_enabled", [False, True], scope="module")
async def test_build_and_deploy(ops_test: OpsTest, rendered_bundle, tls_enabled):
    """Build the charm-under-test and deploy it together with related charms.

    Assert on the unit status before any relations/configurations take place.
    """
    # Add "testing" overlay to deploy avalanche, to have metrics and alerts
    overlays = ["overlays/testing-overlay.yaml"]
    if tls_enabled:
        overlays.extend(["overlays/tls-overlay.yaml"])
    await cli_deploy_bundle(ops_test, str(rendered_bundle), overlays=overlays)

    # Idle period is set to 90 to capture restarts caused by applying resource limits
    # FIXME: raise_on_error should be removed (i.e. set to True) when units stop flapping to error
    await ops_test.model.wait_for_idle(
        status="active", timeout=1000, idle_period=90, raise_on_error=False
    )
    await ops_test.model.wait_for_idle(status="active", timeout=1000, idle_period=90)


@pytest.mark.abort_on_fail
async def test_obtain_external_ca_cert(ops_test):
    return_code, stdout, stderr = await ops_test.juju("status", "--no-color")
    status = stdout
    if "ca/0" in status:
        # Obtain certificate from external-ca
        temp_dir = tempfile.mkdtemp()
        cert_path = Path(temp_dir + "/ca.pem")

        return_code, stdout, stderr = await ops_test.juju(
            *"run ca/0 get-ca-certificate --format=json --no-color".split()
        )
        cert = json.loads(stdout)["ca/0"]["results"]["ca-certificate"]
        cert_path.write_text(cert)

        ctx = ssl.create_default_context()
        ctx.load_verify_locations(cert_path)
        context.external_ca = ctx

    # At this point, a non-None value in context.external_ca can be used as an indication for
    # whether TLS is enabled.


@pytest.mark.abort_on_fail
async def test_web_uis_are_reachable_via_ingress_url(ops_test):
    # Create mapping from app name (as it appears in catalogue) to its url
    # Looks like this:
    # {
    #   'Grafana': 'https://grafana-0.grafana-endpoints.test.svc.cluster.local:3000',
    #   'Prometheus': 'https://prometheus-0.prometheus-endpoints.test.svc.cluster.local:9090',
    #   'Alertmanager': 'https://alertmanager-0.alertmanager-endpoints.test.svc.cluster.local:9093'
    # }
    return_code, stdout, stderr = await ops_test.juju(
        "ssh", "--container", "catalogue", "catalogue/0", "cat", "/web/config.json"
    )
    cat_conf = json.loads(stdout)

    apps = {app["name"]: app["url"] for app in cat_conf["apps"]}

    for name, url in apps.items():
        logger.info("Attempting to reach %s (%s)...", name, url)
        # We intentionally do not want to use "insecure" here, to make sure TLS is set up correctly
        response = urlopen(
            url,
            data=None,
            timeout=2.0,
            context=context.external_ca if url.startswith("https://") else None,
        )
        assert response.code == 200


@pytest.mark.abort_on_fail
async def test_web_uis_are_reachable_via_unit_ip(ops_test: OpsTest):
    """Make sure strip-prefix works as expected so that no path is needed when curling unit ip."""
    for app_name, port, path in [
        ("alertmanager", 9093, "/api/v2/status"),
        ("prometheus", 9090, "/-/ready"),
    ]:
        address = await get_address(ops_test, app_name, 0)
        url = f"{'http' if context.external_ca is None else 'https'}://{address}:{port}{path}"
        logger.info("Attempting to reach %s (%s)...", app_name, url)

        # We always use "insecure" here because we're connecting via unit ip directly.
        response = urlopen(url, data=None, timeout=2.0, context=insecure_context)
        assert response.code == 200


@pytest.mark.abort_on_fail
async def test_prometheus_sees_alertmanager(ops_test: OpsTest):
    prom_url = await get_proxied_url(ops_test, "prometheus", 0)

    response = urlopen(
        f"{prom_url}/api/v1/alertmanagers", data=None, timeout=2.0, context=insecure_context
    )
    assert response.code == 200
    # an empty response looks like this:
    # {"status":"success","data":{"activeAlertmanagers":[],"droppedAlertmanagers":[]}}
    decoded = json.loads(response.read().decode("utf8"))
    # a jsonified activeAlertmanagers looks like this:
    # [{'url': 'http://<ingress:80 or fqdn:9093>/api/v2/alerts'}]
    active_alertmanagers = decoded["data"]["activeAlertmanagers"]
    assert len(active_alertmanagers) == len(ops_test.model.applications["alertmanager"].units)

    # Make sure droppedAlertmanagers is empty
    assert not decoded["data"].get("droppedAlertmanagers")


@pytest.mark.abort_on_fail
async def test_juju_topology_labels_in_alerts(ops_test: OpsTest):
    """For alert labels to reach alertmanager, labels need to be injected and forwarded to prom."""
    alerts = await get_alertmanager_alerts(ops_test, "alertmanager", retries=100)

    i = -1
    for i, alert in enumerate(alerts):
        # make sure every alert has all the juju topology labels
        # NOTE this would only test alerts that are already firing while testing
        assert alert["labels"].keys() >= juju_topology_keys

        # make sure the juju topology entries are not empty
        assert all(alert["labels"][key] for key in juju_topology_keys)

    assert i >= 0  # should have at least one alarms listed (the "AlwaysFiring" alarm rule)
    logger.info("juju topology test passed for %s alerts", i + 1)


@pytest.mark.abort_on_fail
async def test_alerts_are_grouped(ops_test: OpsTest):
    groups = await get_alertmanager_groups(ops_test, "alertmanager", retries=100)
    i = -1
    for i, group in enumerate(groups):
        # make sure all groups are grouped by juju topology keys
        assert group["labels"].keys() == juju_topology_keys

    assert i >= 0  # should have at least one group listed (the "AlwaysFiring" alarm rule)
    logger.info("juju topology grouping test passed for %s groups", i + 1)


@pytest.mark.abort_on_fail
async def test_alerts_are_fired_from_non_leader_units_too(ops_test: OpsTest):
    """The list of alerts must include an "AlwaysFiring" alert from each avalanche unit."""

    async def all_alerts_fire():
        alerts = await get_alertmanager_alerts(
            ops_test,
            "alertmanager",
            retries=100,
        )
        alerts = list(
            filter(
                lambda itm: itm["labels"]["alertname"] == "AlwaysFiringDueToNumericValue", alerts
            )
        )
        units_firing = sorted([alert["labels"]["juju_unit"] for alert in alerts])
        logger.info("Units firing as of this moment: %s", units_firing)
        return units_firing == ["avalanche/0", "avalanche/1"]

    await juju.utils.block_until_with_coroutine(all_alerts_fire, timeout=300, wait_period=15)


@pytest.mark.abort_on_fail
async def test_bundle_charms_can_handle_frequent_update_status(ops_test: OpsTest):
    async with ModelConfigChange(ops_test, **{"update-status-hook-interval": "10s"}):
        # Wait for a considerable amount of time to make sure charms can repeatedly handle this.
        # If all goes well, `wait_for_idle` would raise a timeout error
        soak_time = 2 * 60  # 2 min
        try:
            await ops_test.model.wait_for_idle(
                status="active",
                raise_on_error=True,
                timeout=soak_time,
                idle_period=soak_time,
                check_freq=0.5,
            )
        except asyncio.TimeoutError:
            # Good, this means no error during the soak time
            pass

    # After update-status frequency is restored to default, make sure all charms settle into active
    await ops_test.model.wait_for_idle(status="active")


@pytest.mark.abort_on_fail
async def test_prometheus_scrapes_loki(ops_test: OpsTest):
    """Prometheus should successfully scrape Loki."""
    prom_url = await get_proxied_url(ops_test, "prometheus", 0)

    response = urlopen(
        f"{prom_url}/api/v1/targets", data=None, timeout=2.0, context=insecure_context
    )
    assert response.code == 200
    as_str = response.read().decode("utf8")
    assert "loki" in as_str  # Should appear in the juju_application label
    assert "loki-k8s" in as_str  # Should appear in the juju_charm label
    assert ops_test.model_name in as_str  # Should appear in the juju_model label and job name

    as_dict = json.loads(as_str)["data"]
    assert as_dict["droppedTargets"] == []  # Shouldn't have any dropped targets

    # All jobs should be up
    health = {target["labels"]["job"]: target["health"] for target in as_dict["activeTargets"]}
    assert set(health.values()) == {"up"}

    logger.info("prometheus is successfully scraping loki through traefik")


@pytest.mark.abort_on_fail
async def test_loki_receives_logs(ops_test: OpsTest):
    """Loki should be able to receive logs."""
    loki_url = await get_proxied_url(ops_test, "loki", 0)

    await ops_test.model.deploy("flog-k8s", application_name="flog", channel="edge", trust=True)
    await ops_test.model.wait_for_idle(status="active")
    # Create the relation
    await ops_test.model.add_relation("loki", "flog")

    # Without a sleep, we get an empty response. Need to give promtail some time to stream the logs
    # or for loki to display them.
    await asyncio.gather(ops_test.model.wait_for_idle(status="active"), asyncio.sleep(120))

    # Check that logs are coming in
    url = f"{loki_url}/loki/api/v1/series"
    logger.info("Querying loki at %s...", url)
    response = urlopen(url, context=insecure_context)
    assert response.code == 200
    as_str = response.read().decode("utf8")
    assert "flog-k8s" in as_str
    logger.info("loki is successfully receiving flog logs")


@pytest.mark.xfail
async def test_goss_validate(ops_test: OpsTest):
    # Run the goss validate with json format
    goss_output = sh.goss("-g", "goss/goss.yaml", "--vars", "goss/vars.yaml", "v", "-f", "json")
    # Parse the JSON output to extract the failed checks count
    goss_json = json.loads(goss_output)
    no_errors = goss_json["summary"]["failed-count"] == 0

    assert no_errors
    if not no_errors:
        errored_fields = [result for result in goss_json["results"] if result["result"] != 0]
        logger.info(f"Goss failures:\n\n{errored_fields}")


@pytest.mark.abort_on_fail
async def test_remove(ops_test):
    # WHEN the apps are removed
    apps = list(ops_test.model.applications.values())
    logger.info("Removing apps: %s", apps)
    for app in apps:
        await app.destroy(destroy_storage=True, force=False, no_wait=False)

    # THEN no app goes into error state and the model is empty
    # TODO when the app removal Juju bug is fixed, replace the following with a wait_for_idle
    #  with raise_on_error=True and assert len(ops_test.model.applications) == 0

    # Sometimes it take time to remove an app, and sometimes juju never really finishes
    # removing. Sleep for a bit and then forcing removal.
    await asyncio.sleep(30)
    apps = list(ops_test.model.applications.values())
    logger.info("Removing apps forcefully: %s", apps)
    for app in apps:
        await app.destroy(destroy_storage=True, force=True, no_wait=True)
    await ops_test.model.block_until(lambda: len(ops_test.model.applications) == 0)

    # Note: Removing all apps is also needed to clean the model for the next parametrization.
