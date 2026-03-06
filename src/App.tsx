import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Cartesian3, createWorldTerrainAsync } from "cesium";
import { Viewer } from "resium";
import "./App.css";

const terrainProvider = createWorldTerrainAsync();

function App() {
  return <Viewer terrainProvider={terrainProvider} full />;
}

export default App;
