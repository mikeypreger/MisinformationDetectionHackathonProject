import { useState, useEffect } from 'react';

const NAV_LINKS = [
  { label: 'How it works', href: '#how-it-works' },
  { label: 'About', href: '#about' },
  { label: 'Use cases', href: '#use-cases' },
  { label: 'FAQ', href: '#faq' },
  { label: 'Contact', href: '#contact' },
];

export default function Header() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 24);
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
        scrolled
          ? 'bg-navy-dark/90 backdrop-blur-xl border-b border-white/[0.06]'
          : 'bg-transparent'
      }`}
    >
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Wordmark */}
        <a
          href="#"
          className="flex items-center gap-2.5 group"
          aria-label="MISS INFORMATION — home"
        >
          <ScanIcon className="text-accent/60 group-hover:text-accent transition-colors duration-300" />
          <span className="font-display text-[15px] font-bold tracking-[0.1em] uppercase gradient-brand">
            MISS INFORMATION
          </span>
        </a>

        {/* Desktop navigation */}
        <nav className="hidden md:flex items-center gap-8" aria-label="Primary navigation">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-[13px] font-light text-blue-muted hover:text-white transition-colors duration-200"
            >
              {link.label}
            </a>
          ))}
        </nav>

        {/* CTA + mobile toggle */}
        <div className="flex items-center gap-4">
          <a
            href="#hero"
            className="hidden md:inline-flex items-center text-[13px] font-semibold text-white bg-accent hover:bg-accent-hover px-4 py-2 rounded-[6px] transition-all duration-200 shadow-[0_2px_12px_rgba(230,57,70,0.3)] hover:shadow-[0_4px_18px_rgba(230,57,70,0.45)] focus:outline-none focus:ring-2 focus:ring-accent/40"
          >
            Analyze a post
          </a>

          <button
            className="md:hidden text-white/50 hover:text-white transition-colors p-1.5 -mr-1"
            onClick={() => setMobileOpen((v) => !v)}
            aria-label={mobileOpen ? 'Close menu' : 'Open navigation'}
            aria-expanded={mobileOpen}
          >
            {mobileOpen ? <XIcon /> : <MenuIcon />}
          </button>
        </div>
      </div>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="md:hidden border-t border-white/[0.06] bg-navy-dark/95 backdrop-blur-xl">
          <nav
            className="max-w-6xl mx-auto px-6 py-4 flex flex-col"
            aria-label="Mobile navigation"
          >
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="py-3.5 text-sm font-light text-blue-muted hover:text-white transition-colors border-b border-white/[0.05] last:border-0"
                onClick={() => setMobileOpen(false)}
              >
                {link.label}
              </a>
            ))}
            <a
              href="#hero"
              className="mt-4 text-center text-sm font-semibold text-white bg-accent hover:bg-accent-hover px-4 py-3 rounded-[6px] transition-colors"
              onClick={() => setMobileOpen(false)}
            >
              Analyze a post
            </a>
          </nav>
        </div>
      )}
    </header>
  );
}

function ScanIcon({ className = '' }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      className={className}
      aria-hidden="true"
    >
      <path d="M2 6V3.5A1.5 1.5 0 0 1 3.5 2H6" strokeLinecap="round" />
      <path d="M14 2h2.5A1.5 1.5 0 0 1 18 3.5V6" strokeLinecap="round" />
      <path d="M18 14v2.5A1.5 1.5 0 0 1 16.5 18H14" strokeLinecap="round" />
      <path d="M6 18H3.5A1.5 1.5 0 0 1 2 16.5V14" strokeLinecap="round" />
      <circle cx="10" cy="10" r="3" />
    </svg>
  );
}

function MenuIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 18 18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <path d="M2 4.5h14M2 9h14M2 13.5h14" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 18 18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <path d="M3 3l12 12M15 3L3 15" />
    </svg>
  );
}
