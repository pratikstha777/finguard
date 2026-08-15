# 🛡️ FinGuard: Real-Time Financial Streaming & Fraud Detection Platform

[![Databricks](https://img.shields.io/badge/Databricks-DLT-red?style=flat-square&logo=databricks)](https://databricks.com/)
[![Apache Spark](https://img.shields.io/badge/Apache%20Spark-3.5%2B-orange?style=flat-square&logo=apachespark)](https://spark.apache.org/)
[![Confluent Kafka](https://img.shields.io/badge/Confluent-Kafka-purple?style=flat-square&logo=apachekafka)](https://www.confluent.io/)
[![Delta Lake](https://img.shields.io/badge/Delta%20Lake-3.0-blue?style=flat-square&logo=delta)](https://delta.io/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-brightgreen?style=flat-square&logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-lightgrey.svg?style=flat-square)](LICENSE)

FinGuard is an enterprise-grade, real-time data streaming and automated fraud detection platform built on the **Databricks Lakehouse Platform**. Leveraging **Delta Live Tables (DLT)**, **Apache Kafka (Confluent Cloud)**, **Apache Spark Structured Streaming**, and **Unity Catalog**, FinGuard ingests high-velocity transaction feeds, joins them against streaming watchlist updates, enforces data quality expectations, and triggers instant email alerts for suspicious activity.

---

## 📐 Architecture Overview

The system follows the industry-standard **Medallion Architecture** (Bronze $\rightarrow$ Silver $\rightarrow$ Gold) to transition data from raw, unparsed event streams into validated, business-ready alert analytical datasets.

```text
               ┌────────────────────────┐      ┌────────────────────────┐
               │  Confluent Cloud Kafka │      │  UC Volumes (JSON Feed)│
               └───────────┬────────────┘      └───────────┬────────────┘
                           │                               │
                           ▼                               ▼
                 ┌───────────────────────────────────────────┐
                 │                BRONZE LAYER               │
                 │   - finguard.bronze.transactions          │
                 │   - finguard.bronze.fraud_watchlist       │
                 └─────────────────────┬─────────────────────┘
                                       │
                                       ▼
                 ┌───────────────────────────────────────────┐
                 │                SILVER LAYER               │
                 │   - Schema Parsing & Type Casting         │
                 │   - Data Quality Rules (@dp.expect)       │
                 │   - Casing & Entity Standardizations      │
                 └─────────────────────┬─────────────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                │                                             │
                ▼                                             ▼
  ┌───────────────────────────┐                 ┌───────────────────────────┐
  │         GOLD LAYER        │                 │         GOLD LAYER        │
  │ - Stream-Stream Fraud Join│                 │ - High-Value Thresholds   │
  │ - Watermarked Matching    │                 │ - Windowed Aggregations   │
  └─────────────┬─────────────┘                 └─────────────┬─────────────┘
                │                                             │
                └──────────────────────┬──────────────────────┘
                                       │
                                       ▼
                 ┌───────────────────────────────────────────┐
                 │               ALERTING SINKS              │
                 │   - Decoupled ForeachBatch SMTP Notifier  │
                 │   - HTML Notification Formatting          │
                 └───────────────────────────────────────────┘
```

---

## 🗂️ Project & Directory Structure

```text
finguard-pipeline/
├── README.md                                      # Documentation & Architecture Overview
├── config/
│   └── secret_scope_setup.py                      # Databricks Secret Scope Setup Script
├── pipelines/
│   ├── bronze/
│   │   ├── dlt_bronze_transactions.py             # Kafka continuous stream ingestion
│   │   └── dlt_bronze_watchlist.py                # Auto Loader incremental file ingestion
│   ├── silver/
│   │   ├── dlt_silver_transactions.py             # Schema parsing & DLT quality expectations
│   │   ├── dlt_silver_customers.py                # Customer dimension normalization
│   │   └── dlt_silver_fraud_watchlist.py          # Watchlist cleaning & timestamp conversion
│   └── gold/
│       ├── dlt_gold_fraud_card_alert.py           # Stream-Stream Join (Transactions + Watchlist)
│       ├── dlt_gold_high_value_alert.py           # Threshold-breach alert logic
│       ├── dlt_gold_tumbling_window.py            # 1-minute non-overlapping aggregations
│       └── dlt_gold_sliding_window.py             # 5-minute sliding window aggregations
├── sinks/
│   ├── sink_email_fraud_card.py                   # ForeachBatch SMTP notifier for fraud matches
│   └── sink_email_high_value.py                   # ForeachBatch SMTP notifier for spending limits
├── data_generators/
│   └── fraud_watchlist_generator.py               # Simulated file streamer to Unity Catalog Volume
└── tests/
    ├── test_email_connection.py                   # Sandbox script for SMTP configuration test
    ├── test_kafka_ingestion.py                    # Kafka batch batch-fetch validation
    └── test_autoloader_schema.py                  # Auto Loader schema inference test suite
```

---

## ⚡ Key Engineering & Design Decisions

### 1. Data Quality Engine via DLT Expectations
In `dlt_silver_transactions.py`, incoming records are evaluated in real-time. Invalid payloads missing critical identifiers are quarantined or dropped automatically without interrupting the stream:
* `@dp.expect_or_drop("valid_transaction_id", "transaction_id IS NOT NULL")`
* `@dp.expect_or_drop("valid_customer_id", "customer_id IS NOT NULL")`
* `@dp.expect_or_drop("valid_card_number", "card_number IS NOT NULL")`
* `@dp.expect("valid_amount", "amount > 0")`

### 2. Stream-Stream Join Watermarking & Memory Management
To join real-time transaction streams with streaming fraud watchlists, both streams are configured with 5-minute event-time watermarks and time-range constraint boundaries. This allows Spark's Structured Streaming engine to safely evict old state memory, preventing executor Out-Of-Memory (OOM) errors:

```python
transactions_wm = transactions.withWatermark("transaction_timestamp", "5 minutes")
watchlist_wm = fraud_watchlist.withWatermark("effective_from", "5 minutes")

fraud_detected = transactions_wm.join(
    watchlist_wm,
    (transactions_wm.card_number == watchlist_wm.entity_id) &
    (transactions_wm.transaction_timestamp >= watchlist_wm.effective_from) &
    (transactions_wm.transaction_timestamp <= watchlist_wm.effective_from + F.expr("INTERVAL 7 DAYS")),
    "inner"
)
```





## 🚀 Quickstart & Deployment

### Prerequisites
* Databricks Workspace running **Runtime 13.3 LTS** or higher.
* Unity Catalog enabled with a target catalog named `finguard`.
* Confluent Cloud Kafka topic (`finguard-transactions`).

### Step 1: Databricks Unity Catalog Initialization
Execute the following DDL statements in Databricks SQL Editor:

```sql
CREATE CATALOG IF NOT EXISTS finguard;
CREATE SCHEMA IF NOT EXISTS finguard.bronze;
CREATE SCHEMA IF NOT EXISTS finguard.silver;
CREATE SCHEMA IF NOT EXISTS finguard.gold;

CREATE VOLUME IF NOT EXISTS finguard.source.fraud_watchlist;
```

### Step 2: Create Delta Live Tables Pipeline
1. In Databricks Workspace, navigate to **Delta Live Tables** $
ightarrow$ **Create Pipeline**.
2. Select **Continuous** mode for production real-time processing.
3. Set **Target Catalog** to `finguard` and **Target Schema** to `gold`.
4. Add the notebook file paths located in `/pipelines/` and `/sinks/`.
5. Click **Start** to initialize the continuous pipeline.

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
