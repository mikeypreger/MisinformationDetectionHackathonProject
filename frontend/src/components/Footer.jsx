const PLATFORM_LINKS = [
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Use cases', href: '#use-cases' },
  { label: 'About', href: '#about' },
];

const INFO_LINKS = [
  { label: 'FAQ', href: '#faq' },
  { label: 'Contact', href: '#contact' },
];

export default function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer
      id="contact"
      className="border-t border-white/[0.06] px-6 pt-20 md:pt-24 pb-10"
      aria-label="Site footer"
    >
      <div className="max-w-5xl mx-auto">
        {/* Main grid */}
        <div className="grid md:grid-cols-2 gap-14 items-start mb-16">

          {/* CTA block */}
          <div>
            <p className="text-[10px] font-medium tracking-[0.16em] uppercase text-blue-muted/40 mb-4">
              Contact
            </p>
            <h2 className="text-[24px] sm:text-[30px] font-light text-white mb-5 leading-tight">
              Building tools for clearer visual context.
            </h2>
            <p className="text-[13px] font-light text-blue-muted/60 mb-8 leading-relaxed max-w-sm">
              We are actively developing the backend analysis engine. If you are interested in
              collaboration, research partnerships, or early access — we would like to hear from you.
            </p>
            <div className="flex items-center gap-4 flex-wrap">
              <a
                href="mailto:hello@missinformation.ai"
                className="inline-flex items-center gap-2 bg-accent hover:bg-[#0088cc] text-white text-[13px] font-medium px-5 py-2.5 rounded-lg transition-all duration-200 hover:shadow-lg hover:shadow-accent/20 focus:outline-none focus:ring-2 focus:ring-pale-blue/30"
              >
                Contact us
              </a>
              <a
                href="mailto:hello@missinformation.ai"
                className="text-[13px] font-light text-blue-muted/50 hover:text-blue-muted/80 transition-colors"
              >
                hello@missinformation.ai
              </a>
            </div>
          </div>

          {/* Navigation columns */}
          <div className="grid grid-cols-2 gap-8 md:pt-2">
            <div>
              <p className="text-[9px] font-medium tracking-[0.12em] uppercase text-blue-muted/35 mb-5">
                Platform
              </p>
              <ul className="flex flex-col gap-3.5" role="list">
                {PLATFORM_LINKS.map(({ label, href }) => (
                  <li key={label}>
                    <a
                      href={href}
                      className="text-[13px] font-light text-blue-muted/55 hover:text-white transition-colors duration-200"
                    >
                      {label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-[9px] font-medium tracking-[0.12em] uppercase text-blue-muted/35 mb-5">
                Info
              </p>
              <ul className="flex flex-col gap-3.5" role="list">
                {INFO_LINKS.map(({ label, href }) => (
                  <li key={label}>
                    <a
                      href={href}
                      className="text-[13px] font-light text-blue-muted/55 hover:text-white transition-colors duration-200"
                    >
                      {label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="border-t border-white/[0.05] pt-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <a
            href="#"
            className="flex items-center gap-2 group"
            aria-label="miss information — back to top"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 20 20"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.3"
              className="text-pale-blue/25 group-hover:text-pale-blue/45 transition-colors duration-300"
              aria-hidden="true"
            >
              <rect x="2.5" y="2.5" width="15" height="15" rx="2" />
              <rect x="6.5" y="6.5" width="7" height="7" rx="1" />
            </svg>
            <span className="text-[12px] font-light text-blue-muted/35 group-hover:text-blue-muted/55 transition-colors duration-300">
              miss information
            </span>
          </a>

          <p className="text-[11px] font-light text-blue-muted/28">
            © {year} miss information. Visual context analysis.
          </p>
        </div>
      </div>
    </footer>
  );
}
