# Usage
Note: `astronomer/airflow-chart==0.20.1` is in the `astronomer/astronomer==0.25.11` chart
<https://github.com/astronomer/astronomer/blob/v0.25.11/charts/astronomer/values.yaml#L8>

```shell
helm repo add astronomer https://helm.astronomer.io
helm repo update
helm pull astronomer/astronomer --untar --version=0.25.11
helm pull astronomer/airflow --untar --version=0.20.1
INCLUDE_CHART_MUSEUM=false INCLUDE_NGINX_ASTRONOMER_CERTIFIED=false INCLUDE_PRIVATE_CA_ALPINE=false SHOULD_CREATE_AIRGAP_IMAGES_YAML=false \
  python extract_images.py
python reassemble.py
```

# Output
`images.txt`
```shell
quay.io/astronomer/ap-configmap-reloader:0.5.0
quay.io/astronomer/ap-elasticsearch:7.10.2-3
quay.io/astronomer/ap-pgbouncer-exporter:0.11.0-1
quay.io/astronomer/ap-kube-state:1.7.2
quay.io/astronomer/ap-keda-metrics-adapter:1.3.0
quay.io/astronomer/ap-curator:5.8.4-4
quay.io/astronomer/ap-elasticsearch-exporter:1.2.1
quay.io/astronomer/ap-nginx:0.49.0-1
quay.io/astronomer/ap-alertmanager:0.23.0
quay.io/astronomer/ap-airflow:None
quay.io/astronomer/ap-pgbouncer:1.8.1
quay.io/astronomer/ap-db-bootstrapper:0.25.1
quay.io/astronomer/ap-blackbox-exporter:0.19.0-3
quay.io/astronomer/ap-nginx-es:3.13.5-4
quay.io/astronomer/ap-nats-streaming:0.22.0-1
quay.io/astronomer/ap-prometheus:2.21.0
quay.io/astronomer/ap-base:3.14.1
quay.io/astronomer/ap-registry:3.14.2-2
quay.io/astronomer/ap-astro-ui:0.25.4
quay.io/astronomer/ap-commander:0.25.3
quay.io/prometheus/node-exporter:v1.2.2
quay.io/astronomer/ap-statsd-exporter:0.18.0
quay.io/astronomer/ap-nats-exporter:0.8.0
quay.io/astronomer/ap-airflow:2.0.0-buster
quay.io/astronomer/ap-houston-api:0.25.13
quay.io/astronomer/ap-base:3.14.1
quay.io/astronomer/ap-keda:1.3.0
quay.io/astronomer/ap-postgres-exporter:3.13.5
quay.io/astronomer/ap-grafana:7.5.10
quay.io/astronomer/ap-redis:6.2.5-1
quay.io/astronomer/ap-nats-exporter:0.8.0
quay.io/astronomer/ap-fluentd:1.13.3-4
quay.io/astronomer/ap-kubed:0.12.0
quay.io/astronomer/ap-kibana:7.10.2-2
quay.io/astronomer/ap-default-backend:0.25.2
quay.io/astronomer/ap-nats-server:2.3.2-2
quay.io/astronomer/ap-cli-install:0.25.2
quay.io/astronomer/ap-db-bootstrapper:0.25.1
```