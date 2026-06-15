# Cost management

## Where the money goes

1. **Compute (Databricks DBUs).** ~85% of total spend.
2. **Storage (S3).** ~10%.
3. **Lakebase + Unity Catalog** services. ~5%.

Focus on compute.

## The five rules

1. **Right-size clusters.** Most jobs are over-provisioned. Start with
   the platform default (2 workers, autoscale to 10) and only grow if
   Spark UI shows sustained high CPU.

2. **Use spot instances in dev + staging.** ~70% cheaper. Tasks retry
   on pre-emption, so non-critical work tolerates it well.

3. **Schedule expensive jobs at off-peak.** Singapore region has lowest
   contention 02:00–07:00 SGT.

4. **Stop interactive clusters when you're done.** All-purpose clusters
   cost ~3× job clusters per DBU. They also tend to be left running.
   The platform-team script `auto_terminate_idle_clusters.py` runs
   hourly and stops anything idle > 30 minutes.

5. **Photon for SQL-heavy workloads.** ~2× speed at the same cost. On
   by default in the platform variables.

## What's expensive

| Operation | Why |
|---|---|
| `df.collect()` on a big DataFrame | Driver memory + network |
| Repeated reads of the same table | Reads cost DBU + S3 requests |
| Tiny files (< 100 MB) on writes | Compaction overhead |
| Cross-region reads | Egress fees |
| Streaming jobs left running with no input | Cluster sits idle, still bills |

## Tagging + chargeback

Every cluster carries tags set by the platform team:

```
cdo:team    = finance | supplier | infra
cdo:app     = finance-payment-recon
cdo:env     = dev | staging | prod
cdo:cost-ctr = <Jira project>
```

Cost is allocated to teams via these tags in the monthly Databricks
billing export to `system.billing.usage`.

## Monthly review

Platform team publishes a cost-by-team table to the leadership channel
on the first of each month. Spikes get followed up with the responsible
team; trends inform the next quarter's capacity planning.
