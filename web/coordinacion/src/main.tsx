import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./vendor/bootstrap-grid.min.css";
import "./estilos.css";
import "./estilo/marca.css";
import "./estilo/acceso.css";
import "./estilo/marco.css";
import "./estilo/inicio.css";
import "./estilo/pendientes.css";
import "./estilo/vistas.css";
import "./estilo/impacto.css";
import "./estilo/controles.css";
import "./motion/animaciones.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
