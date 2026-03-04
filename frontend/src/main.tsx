import "@radix-ui/themes/styles.css";
import "./index.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { Theme } from "@radix-ui/themes";
import App from "./App";
import { THEME } from "./lib/theme";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter basename="/app">
      <Theme
        accentColor={THEME.accentColor}
        grayColor={THEME.grayColor}
        radius={THEME.radius}
        scaling={THEME.scaling}
        appearance="light"
      >
        <App />
      </Theme>
    </BrowserRouter>
  </StrictMode>
);
