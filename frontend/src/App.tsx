import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import ComingSoon from "./pages/ComingSoon";
import Analyst from "./pages/Analyst";
import Documents from "./pages/Documents";

const stub = (title: string, note: string) => <ComingSoon title={title} note={note} />;

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="documents" element={<Documents />} />
        <Route path="analyst" element={<Analyst />} />
        <Route path="metrics" element={stub("Financial Metrics", "Extracted metrics and charts. Arrives with the metrics phase.")} />
        <Route path="comparisons" element={stub("Comparisons", "Compare periods and companies. Arrives with the comparison tool.")} />
        <Route path="reports" element={stub("Reports", "Generated summaries. Arrives with the summarizer tool.")} />
        <Route path="history" element={stub("Chat History", "Past conversations. Arrives with the chat phase.")} />
        <Route path="settings" element={stub("Settings", "Model and display preferences.")} />
      </Route>
    </Routes>
  );
}
