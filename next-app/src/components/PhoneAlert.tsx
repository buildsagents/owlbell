/** Signature visual — owner's phone receiving a booked-job alert. */
export default function PhoneAlert() {
  return (
    <div className="phone-alert" aria-hidden>
      <div className="phone-alert-device">
        <div className="phone-alert-status">
          <span>11:04 PM</span>
          <span className="phone-alert-signal">
            <span />
            <span />
            <span />
            <span />
          </span>
        </div>
        <div className="phone-alert-screen">
          <p className="phone-alert-time">Fri · After hours</p>
          <div className="phone-alert-notification">
            <div className="phone-alert-notif-head">
              <span className="phone-alert-app">Owlbell</span>
              <span>now</span>
            </div>
            <p className="phone-alert-notif-title">Job booked — burst pipe</p>
            <p className="phone-alert-notif-body">
              Michael T. · 11:00 AM tomorrow · ~$850 est. · (303) 555-0187
            </p>
          </div>
          <div className="phone-alert-call-chip">
            <span className="phone-alert-call-dot" />
            Call answered in 1.8s
          </div>
        </div>
      </div>
      <p className="phone-alert-caption">What lands on your phone while you&apos;re on a job</p>
    </div>
  );
}