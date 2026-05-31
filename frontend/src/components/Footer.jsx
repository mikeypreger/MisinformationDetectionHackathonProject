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
            <h2 className="font-display text-[24px] sm:text-[30px] font-semibold text-white mb-5 leading-tight">
              Advancing the fight against visual misinformation.
            </h2>
            <p className="text-[13px] font-light text-blue-muted/60 mb-8 leading-relaxed max-w-sm">
              Our analysis engine is under active development. We welcome inquiries from researchers,
              journalists, and organizations interested in collaboration, early access, or research
              partnerships.
            </p>
            <div className="flex items-center gap-4 flex-wrap">
              <a
                href="mailto:hello@missinformation.ai"
                className="inline-flex items-center gap-2 bg-accent hover:bg-accent-hover text-white text-[13px] font-semibold px-5 py-2.5 rounded-lg transition-all duration-200 shadow-[0_2px_14px_rgba(230,57,70,0.3)] hover:shadow-[0_4px_20px_rgba(230,57,70,0.45)] focus:outline-none focus:ring-2 focus:ring-accent/40"
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
        <div className="border-t border-white/[0.05] pt-8 flex flex-col gap-3">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <a
              href="#"
              className="flex items-center gap-2 group"
              aria-label="MISS INFORMATION — back to top"
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 20 20"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.4"
                className="text-accent/35 group-hover:text-accent/65 transition-colors duration-300"
                aria-hidden="true"
              >
                <path d="M2 6V3.5A1.5 1.5 0 0 1 3.5 2H6" strokeLinecap="round" />
                <path d="M14 2h2.5A1.5 1.5 0 0 1 18 3.5V6" strokeLinecap="round" />
                <path d="M18 14v2.5A1.5 1.5 0 0 1 16.5 18H14" strokeLinecap="round" />
                <path d="M6 18H3.5A1.5 1.5 0 0 1 2 16.5V14" strokeLinecap="round" />
                <circle cx="10" cy="10" r="3" />
              </svg>
              <span className="font-display text-[12px] font-bold tracking-[0.1em] uppercase gradient-brand opacity-50 group-hover:opacity-80 transition-opacity duration-300">
                MISS INFORMATION
              </span>
            </a>

            <p className="text-[11px] font-light text-blue-muted/28">
              © {year} MISS INFORMATION. Visual context analysis.
            </p>
          </div>

          <p className="text-center sm:text-right text-[11px] font-light text-blue-muted/22 tracking-wide">
            HUJI Hackathon 2026 &mdash; Itamar Galpern, Michael Preger, Adi Ozana, Yair Israel
          </p>
        </div>
      </div>
    </footer>
  );
}
