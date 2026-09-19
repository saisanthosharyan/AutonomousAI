import { useLocation } from "react-router-dom";
import ChatBox from "../components/dashboard/ChatBox";

export default function Home() {
  const location = useLocation();

  return (
    <ChatBox
      key={`${location.pathname}-${location.key}`}
    />
  );
}
