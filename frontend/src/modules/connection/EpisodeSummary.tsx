import type { EpisodeReport } from "./api";

export default function EpisodeSummary({ report }: { report: EpisodeReport }) {
  return (
    <section className="connection-card" aria-label="Last real episode report">
      <h2>
        Last real episode ·{" "}
        {report.outcome === "completed" ? "Completed" : "Stopped"}
      </h2>
      <p>{report.reason}</p>
      <p className="connection-hint">
        {report.samples} measured samples · {report.duration_s.toFixed(1)} s
        elapsed.
        {report.last_sample_age_s !== null &&
          ` Last sample was ${(report.last_sample_age_s * 1000).toFixed(0)} ms old when the run ended.`}
      </p>
      {report.joints.length ? (
        <div className="connection-table-wrap">
          <table>
            <caption>Angles in degrees · signed error = encoder − Gym</caption>
            <thead>
              <tr>
                <th>Joint</th>
                <th>Last Gym</th>
                <th>Last encoder</th>
                <th>Last error</th>
                <th>Peak error</th>
                <th>RMS error</th>
              </tr>
            </thead>
            <tbody>
              {report.joints.map((joint) => (
                <tr key={joint.name}>
                  <th>{joint.name.replaceAll("_", " ")}</th>
                  <td>{joint.last_gym_deg.toFixed(2)}</td>
                  <td>{joint.last_measured_deg.toFixed(2)}</td>
                  <td>{joint.last_error_deg.toFixed(2)}</td>
                  <td>{joint.max_abs_error_deg.toFixed(2)}</td>
                  <td>{joint.rmse_deg.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p>No measured samples were captured.</p>
      )}
      <p className="connection-hint">
        Encoder comparison does not independently verify the physical link
        geometry or object placement.
      </p>
    </section>
  );
}
