import { DISPATCH_LIVE_ROWS, type DispatchRow } from "@/lib/plumbing-scenarios";

const STATUS_LABEL: Record<DispatchRow["status"], string> = {
  booked: "Booked",
  emergency: "Emergency",
  callback: "Callback",
  answered: "Answered",
};

type Props = {
  compact?: boolean;
  title?: string;
  subtitle?: string;
};

export default function DispatchBoard({
  compact = false,
  title = "Live call board",
  subtitle = "Friday - After hours - Bristol",
}: Props) {
  const rows = compact ? DISPATCH_LIVE_ROWS.slice(0, 3) : DISPATCH_LIVE_ROWS;

  return (
    <div className={`ops-board${compact ? " ops-board--compact" : ""}`}>
      <header className="ops-board-head">
        <div>
          <p className="ops-board-kicker">Owlbell dispatch</p>
          <h3 className="ops-board-title">{title}</h3>
          <p className="ops-board-sub">{subtitle}</p>
        </div>
        <div className="ops-board-live">
          <span className="ops-board-live-dot" aria-hidden />
          3 live
        </div>
      </header>

      <div className="ops-board-stats" aria-hidden={compact}>
        <div>
          <span className="ops-board-stat-label">Answered</span>
          <span className="ops-board-stat-value num">100%</span>
        </div>
        <div>
          <span className="ops-board-stat-label">Avg pickup</span>
          <span className="ops-board-stat-value num">1.8s</span>
        </div>
        <div>
          <span className="ops-board-stat-label">Booked tonight</span>
          <span className="ops-board-stat-value num">2</span>
        </div>
      </div>

      <div className="ops-board-table-wrap" role="region" aria-label="Recent calls">
        <table className="ops-board-table">
          <thead>
            <tr>
              <th scope="col">Time</th>
              <th scope="col">Caller</th>
              <th scope="col">Issue</th>
              {!compact && <th scope="col">Address</th>}
              <th scope="col">Status</th>
              <th scope="col" className="ops-board-col-value">
                Est.
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td className="num">{row.time}</td>
                <td>{row.caller}</td>
                <td className="ops-board-issue">{row.issue}</td>
                {!compact && <td className="ops-board-address">{row.address}</td>}
                <td>
                  <span className={`ops-status ops-status--${row.status}`}>
                    {STATUS_LABEL[row.status]}
                  </span>
                </td>
                <td className="num ops-board-col-value">{row.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <footer className="ops-board-foot">
        <span className="ops-board-foot-item">
          <span className="ops-board-foot-dot ops-board-foot-dot--sms" aria-hidden />
          Owner SMS on every booked job
        </span>
        <span className="ops-board-foot-item num">4 calls - 0 voicemail</span>
      </footer>
    </div>
  );
}
