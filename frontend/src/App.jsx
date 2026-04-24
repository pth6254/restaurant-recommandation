import { Routes, Route } from "react-router-dom";
import ChatPage  from "./pages/ChatPage";
import SharePage from "./pages/SharePage";

export default function App() {
  return (
    <Routes>
      <Route path="/"              element={<ChatPage />} />
      <Route path="/share/:code"   element={<SharePage />} />
    </Routes>
  );
}
