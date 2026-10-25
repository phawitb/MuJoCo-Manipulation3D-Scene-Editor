import type { EpisodeReport } from "./api";

export default function EpisodeSummary({ report }: { report: EpisodeReport }) {
  return (
    <section className="connection-card" aria-label="Last real episode report">
      <h2>
        Last real episode ·{" "}
        {report.outcome === "completed" ? "Tool goals reached" : "Stopped"}
      </h2>
      <p>{report.reason}</p>
      <p className="connection-hint">
        {report.samples} encoder samples · {report.duration_s.toFixed(1)} s
        elapsed.
        {report.last_sample_age_s !== null &&
          ` Last sample ${(report.last_sample_age_s * 1000).toFixed(0)} ms old at completion.`}
      </p>
      {report.last_error ? (
        <div className="connection-metrics">
          <span>
            Final position error{" "}
            <strong>{report.last_error.position_mm.toFixed(2)} mm</strong>
          </span>
          <span>
            Final orientation error{" "}
            <strong>{report.last_error.orientation_deg.toFixed(2)}°</strong>
          </span>
          <span>
            Final jaw error{" "}
            <strong>{report.last_error.opening_deg.toFixed(2)}°</strong>
          </span>
        </div>
      ) : (
        <p>No measured samples were captured.</p>
      )}
      <p className="connection-hint">
        Encoder estimate · collision geometry from the scene rehearsal. Physical
        grasp and object placement have not been independently verified.
      </p>
    </section>
  );
}
