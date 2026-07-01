type Props = {
  time: string;
  context: string;
  title: string;
  body: string;
  chip: string;
};

/** Compact SMS screenshot mockup for proof section. */
export default function BookedJobSmsCard({ time, context, title, body, chip }: Props) {
  return (
    <figure className="proof-sms-card">
      <div className="phone-alert-device proof-sms-device">
        <div className="phone-alert-status">
          <span>{time}</span>
          <span className="phone-alert-signal">
            <span />
            <span />
            <span />
            <span />
          </span>
        </div>
        <div className="phone-alert-screen">
          <p className="phone-alert-time">{context}</p>
          <div className="phone-alert-notification">
            <div className="phone-alert-notif-head">
              <span className="phone-alert-app">Owlbell</span>
              <span>now</span>
            </div>
            <p className="phone-alert-notif-title">{title}</p>
            <p className="phone-alert-notif-body">{body}</p>
          </div>
          <div className="phone-alert-call-chip">
            <span className="phone-alert-call-dot" />
            {chip}
          </div>
        </div>
      </div>
      <figcaption className="proof-sms-caption">Anonymized owner SMS screenshot</figcaption>
    </figure>
  );
}