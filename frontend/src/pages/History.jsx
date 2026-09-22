import { History as HistoryIcon, Sparkles } from "lucide-react";

export default function History() {
  return (
    <div className="aio-workspace">
      <div className="aio-main">
        <section className="aio-history-page">
          <div className="aio-history-header">
            <div className="aio-section-label">
              <HistoryIcon size={12} />
              BUILD HISTORY
            </div>

            <h1>Build History</h1>

            <p>
              View your previous AutoDev AI project generations and
              build activity.
            </p>
          </div>

          <div className="aio-history-empty">
            <div className="aio-history-empty-icon">
              <Sparkles size={20} />
            </div>

            <h2>No build history yet</h2>

            <p>
              Projects you generate with AutoDev AI will appear here.
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}