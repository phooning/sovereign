# Sovereign (WIP)

An open-source global swarm control information center. This project aims to address the constrained angle question: what if we have to track and task millions of drones, at tens of thousands of miles apart, all operating complex tasks in multiple swarms? Many optimizers at scale must be built to answer that problem.

Notwithstanding the fact that you:
- Have a lot of drones at your disposal.
- Have satellite communication with them.
- Have data ingestion and task control needs.

## Get Started

```sh
nvm install latest
npm i -pnpm

# Install dependencies and launch the desktop app.
pnpm i
pnpm tauri dev
```

## Overview

|Feature       |Tool                                             |Purpose                                                         |
|--------------|-------------------------------------------------|----------------------------------------------------------------|
|Map           |[CesiumJS](https://cesium.com/platform/cesiumjs/)|Aviation-standard Ellipsoid WGS84 Earth Model                   |
|Data Ingestion|[NATS](https://nats.io/)                         |Handle millions of messages per second with millisecond latency.|
|Database      |[QuestDB](https://questdb.com/)                  |Store high-cardinal time series data.                           |
|Consensus     |[rafts](https://raft.github.io/)                 |Designated leader consensus algorithm.                          |
|Observability|[OpenTelemetry](https://opentelemetry.io/)|Distributed tracing and command correlation|
