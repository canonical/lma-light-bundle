avalanche_metric_count   = 100
num_avalanche_targets    = 5

locust_log_lines_per_sec = 0

disk_type = "pd-ssd"
ncpus     = 4
gbmem     = 8


# 2021-12-08 pd-ssd-4cpu-8gb
#
# avalanche_metric_count = 100
# num_avalanche_targets = 5
# prom_scrape_interval = 15
# datapoints/min = 20,000
# # locust = 20
# big query period = 10 min
# % CPU = 20%
# % mem = 6.91G / 7.76G (90%)
# network: sent 1.8MiB/s, recv 0.02MiB/s
# write = 0.5MiB/s ~ 25 IOPS (steady state)
# read = 0.5MiB/s ~ 4 IOPS (steady state); 12MiB/s ~ 255 IOPS
#
# Occasionally (2-2.5hrs) the VM would hang and prom get oomkilled.
# With the latest prom/prometheus image, encountered a 2-hour hang.
#
# Finding:
# Download size is 200M, not 100M as thought previously. Maybe related toscrape interval being
# reduced from 60s to 15s but locust query remained the same. Can't see why scrape interval would
# change size of interpolated data.


# 2021-12-10 pd-ssd-4cpu-8gb
# Now the size of the "big query" is only 11k points (reduction by a factor of 20 from before)
# avalanche_metric_count = 100
# num_avalanche_targets = 5
# prom_scrape_interval = 15
# datapoints/min = 20,000
# # locust = 20
# big query period = 5 min
# % CPU =
# % mem =
# network: sent X MiB/s, recv X MiB/s
# write = X MiB/s ~ X IOPS (steady state)
# read = X MiB/s ~ X IOPS (steady state); X MiB/s ~ X IOPS
