import ReactDOM from "react-dom/client";
import App from "./App";
import "@fontsource-variable/dm-sans";
import "@fontsource-variable/space-grotesk";
import "./styles.css";
// Avoid duplicate dev WebSocket sessions; the connection hook owns its lifecycle.
ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
