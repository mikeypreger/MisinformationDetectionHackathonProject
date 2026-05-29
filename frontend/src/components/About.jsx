import SectionHeader from './SectionHeader';

const CAPABILITY_ROWS = [
  { label: 'Image verification', value: 'Active' },
  { label: 'Context risk assessment', value: 'Assessed' },
  { label: 'Source framing analysis', value: 'Analyzed' },
  { label: 'Visual metadata extraction', value: 'Processed' },
  { label: 'Cross-reference matching', value: 'Pending' },
];

export default function About() {
  return (
    <section
      id="about"
      className="px-6 py-24 md:py-32 border-t border-white/[0.05]"
      aria-labelledby="about-title"
    >
      <div className="max-w-5xl mx-auto">
        <div className="grid md:grid-cols-2 gap-12 md:gap-20 items-start">
          {/* Copy */}
          <div>
            <SectionHeader
              eyebrow="About"
              title="Built for a world where images travel faster than context."
              id="about-title"
            />
            <p className="text-[14px] font-light text-blue-muted/72 leading-relaxed mb-5">
              miss information is designed for a world where images travel faster than their original
              context. The platform helps users, researchers, journalists, and everyday readers
              examine whether a social media image is being used accurately or misleadingly.
            </p>
            <p className="text-[14px] font-light text-blue-muted/55 leading-relaxed">
              We believe that context is not optional — it is the difference between information and
              misinformation. Our approach combines visual analysis with source framing signals to
              provide a structured, evidence-based perspective on how images circulate across social
              media.
            </p>
          </div>

          {/* Capabilities panel */}
          <div
            className="border border-white/[0.07] rounded-2xl p-6 bg-white/[0.02]"
            aria-label="Platform capabilities"
          >
            <p className="text-[10px] font-medium tracking-[0.14em] uppercase text-blue-muted/40 mb-5">
              Platform capabilities
            </p>
            <ul role="list" className="flex flex-col">
              {CAPABILITY_ROWS.map(({ label, value }) => (
                <li
                  key={label}
                  className="flex items-center justify-between py-3.5 border-b border-white/[0.05] last:border-0"
                >
                  <span className="text-[13px] font-light text-blue-muted/65">{label}</span>
                  <span
                    className={`text-[10px] font-medium border rounded px-2 py-0.5 ${
                      value === 'Pending'
                        ? 'text-blue-muted/40 border-white/[0.07] bg-white/[0.02]'
                        : 'text-pale-blue/65 border-pale-blue/14 bg-pale-blue/[0.06]'
                    }`}
                  >
                    {value}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
