const RISK_CONFIG = {
  Low: {
    color: 'text-emerald-400',
    bg: 'bg-emerald-400/[0.08]',
    border: 'border-emerald-400/20',
    dot: 'bg-emerald-400',
    bar: 'bg-emerald-400/50',
  },
  Medium: {
    color: 'text-amber-400',
    bg: 'bg-amber-400/[0.08]',
    border: 'border-amber-400/20',
    dot: 'bg-amber-400',
    bar: 'bg-amber-400/50',
  },
  High: {
    color: 'text-red-400',
    bg: 'bg-red-400/[0.08]',
    border: 'border-red-400/20',
    dot: 'bg-red-400',
    bar: 'bg-red-400/50',
  },
};

function getHostname(url) {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

export default function ResultCard({ result, url, onReset }) {
  const risk = RISK_CONFIG[result.contextRisk] ?? RISK_CONFIG.Medium;
  const confidence = Math.max(0, Math.min(100, result.confidence));

  return (
    <section
      id="result"
      className="px-6 pb-20 animate-slide-up"
      aria-label="Analysis result"
    >
      <div className="max-w-5xl mx-auto">
        {/* Divider */}
        <div className="flex items-center gap-4 mb-8" aria-hidden="true">
          <div className="h-px flex-1 bg-white/[0.06]" />
          <span className="text-[10px] font-medium tracking-[0.14em] uppercase text-blue-muted/40">
            Analysis result
          </span>
          <div className="h-px flex-1 bg-white/[0.06]" />
        </div>

        {/* Main card */}
        <div className="rounded-2xl border border-white/[0.08] bg-white/[0.025] overflow-hidden">
          <div className="grid md:grid-cols-[5fr_7fr]">

            {/* ─── Image panel ─── */}
            <div className="relative bg-navy-dark/50 border-b md:border-b-0 md:border-r border-white/[0.06] flex flex-col">
              <div className="relative flex-1 min-h-[240px] md:min-h-[420px]">
                <img
                  src={result.imageUrl}
                  alt={result.imageAlt}
                  className="absolute inset-0 w-full h-full object-cover"
                  loading="lazy"
                />
                {/* Gradient overlay */}
                <div className="absolute inset-0 bg-gradient-to-t from-navy-dark/70 via-transparent to-transparent" />

                {/* Source badge */}
                <div className="absolute bottom-3 left-3 right-3">
                  <div className="inline-flex items-center gap-2 bg-navy-dark/80 backdrop-blur-sm border border-white/[0.08] rounded-md px-2.5 py-1.5 max-w-full overflow-hidden">
                    <GlobeIcon className="text-blue-muted/50 flex-shrink-0" />
                    <span className="text-[10px] font-light text-blue-muted/65 truncate">
                      {getHostname(url)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Image metadata strip */}
              <div className="px-5 py-4 border-t border-white/[0.06] flex items-center gap-5 flex-wrap">
                {[
                  { label: 'Platform', value: result.metadata.platform },
                  { label: 'Resolution', value: result.metadata.imageResolution },
                  { label: 'Analysis time', value: result.metadata.analysisTime },
                ].map(({ label, value }) => (
                  <div key={label}>
                    <p className="text-[9px] uppercase tracking-[0.1em] text-blue-muted/35 font-medium mb-0.5">
                      {label}
                    </p>
                    <p className="text-[11px] font-light text-blue-muted/60">{value}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* ─── Analysis panel ─── */}
            <div className="p-6 md:p-8 flex flex-col gap-6">

              {/* Risk + Confidence row */}
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                  <p className="text-[9px] font-medium tracking-[0.14em] uppercase text-blue-muted/40 mb-2">
                    Context risk
                  </p>
                  <div
                    className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-md border text-[13px] font-medium ${risk.color} ${risk.bg} ${risk.border}`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${risk.dot} animate-pulse`} aria-hidden="true" />
                    {result.contextRisk}
                  </div>
                </div>

                <div className="text-right">
                  <p className="text-[9px] font-medium tracking-[0.14em] uppercase text-blue-muted/40 mb-2">
                    Confidence
                  </p>
                  <p className="text-[26px] font-light text-white leading-none tabular-nums mb-2">
                    {confidence}%
                  </p>
                  <div
                    className="w-24 h-[3px] bg-white/[0.07] rounded-full ml-auto overflow-hidden"
                    role="progressbar"
                    aria-valuenow={confidence}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`Confidence: ${confidence}%`}
                  >
                    <div
                      className={`h-full rounded-full transition-all duration-1000 ease-out ${risk.bar}`}
                      style={{ width: `${confidence}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* Verdict + Analysis */}
              <div className="border-t border-white/[0.06] pt-6">
                <p className="text-[16px] sm:text-[17px] font-light text-white leading-snug mb-3">
                  {result.verdict}
                </p>
                <p className="text-[13px] font-light text-blue-muted/75 leading-relaxed">
                  {result.analysis}
                </p>
              </div>

              {/* Key signals */}
              <div>
                <p className="text-[9px] font-medium tracking-[0.14em] uppercase text-blue-muted/40 mb-3">
                  Key signals
                </p>
                <ul className="flex flex-col gap-2.5" role="list">
                  {result.signals.map((signal) => (
                    <li
                      key={signal}
                      className="flex items-center gap-3 text-[13px] font-light text-blue-muted/80"
                    >
                      <span
                        className="w-[5px] h-[5px] rounded-full bg-accent/60 flex-shrink-0"
                        aria-hidden="true"
                      />
                      {signal}
                    </li>
                  ))}
                </ul>
              </div>

              {/* Next steps */}
              <div className="border-t border-white/[0.06] pt-5">
                <p className="text-[9px] font-medium tracking-[0.14em] uppercase text-blue-muted/40 mb-3">
                  Suggested next steps
                </p>
                <ol className="flex flex-col gap-2.5" role="list">
                  {result.nextSteps.map((step, i) => (
                    <li
                      key={step}
                      className="flex items-center gap-3 text-[13px] font-light text-blue-muted/75"
                    >
                      <span
                        className="flex-shrink-0 w-5 h-5 rounded-full border border-white/[0.1] flex items-center justify-center text-[9px] text-blue-muted/50 tabular-nums font-medium"
                        aria-hidden="true"
                      >
                        {i + 1}
                      </span>
                      {step}
                    </li>
                  ))}
                </ol>
              </div>

              {/* Footer */}
              <div className="border-t border-white/[0.06] pt-4 flex items-center justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-1.5">
                  <span
                    className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                      result.metadata.sourceVerified ? 'bg-emerald-400' : 'bg-blue-muted/30'
                    }`}
                    aria-hidden="true"
                  />
                  <span className="text-[11px] font-light text-blue-muted/45">
                    {result.metadata.sourceVerified ? 'Source verified' : 'Source unverified'}
                  </span>
                </div>
                <button
                  onClick={onReset}
                  className="text-[12px] font-light text-blue-muted/45 hover:text-blue-muted transition-colors border border-white/[0.07] hover:border-white/[0.14] px-3 py-1.5 rounded-md"
                >
                  New analysis
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Disclaimer */}
        <p className="mt-4 text-center text-[11px] font-light text-blue-muted/30">
          Mocked result for demonstration. Backend analysis pipeline not yet connected.
        </p>
      </div>
    </section>
  );
}

function GlobeIcon({ className = '' }) {
  return (
    <svg
      width="10"
      height="10"
      viewBox="0 0 12 12"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.2"
      strokeLinecap="round"
      className={className}
      aria-hidden="true"
    >
      <circle cx="6" cy="6" r="5" />
      <path d="M1 6h10M6 1C4.8 2.7 4 4.3 4 6s.8 3.3 2 5M6 1c1.2 1.7 2 3.3 2 5s-.8 3.3-2 5" />
    </svg>
  );
}
