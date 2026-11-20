import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./vendor/bootstrap-grid.min.css";
import "./estilos.css";
import "./ecoconecta.css";
import "./estilo/marca.css";
import "./estilo/acceso.css";
import "./motion/animaciones.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
