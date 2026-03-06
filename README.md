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

Overall, React and the browser environment simply cannot handle the logic for culling and displaying millions of objects (video feeds, NATO symbols, open source intelligence markers, etc). It must be treated only as a small display arm for Rust to decide. The "world state" of telemetry, spatial indexing, and heavy lifting is done in the backend to optimize the sent buffers based on the camera frustrum from the frontend. Therefore:

- Even the Cesium `Entity` API cannot be used - we must generate `czml` packets ourselves for Cesium to process.
- Stream videos through the ffmpeg socket.
- Rely on a least-minimal optimization architecture by the time it shows up on screen, heavy culling should already be processed by Rust.