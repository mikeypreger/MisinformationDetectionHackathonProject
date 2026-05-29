import SectionHeader from './SectionHeader';

const STEPS = [
  {
    number: '01',
    title: 'Paste a post URL',
    description: 'Submit a link to a public social media post containing an image.',
    icon: (
      <svg
        width="20"
        height="20"
        viewBox="0 0 20 20"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.25"
        aria-hidden="true"
      >
        <rect x="2" y="2" width="16" height="16" rx="2" />
        <path d="M5.5 7h9M5.5 10h9M5.5 13h5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    number: '02',
    title: 'Extract visual context',
    description:
      'The system identifies the image from the post and prepares it for contextual analysis.',
    icon: (
      <svg
        width="20"
        height="20"
        viewBox="0 0 20 20"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.25"
        aria-hidden="true"
      >
        <rect x="2" y="2" width="16" height="16" rx="2" />
        <circle cx="10" cy="10" r="3" />
        <path d="M2 7h2M2 13h2M16 7h2M16 13h2M7 2v2M13 2v2M7 16v2M13 16v2" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    number: '03',
    title: 'Review the analysis',
    description:
      'Receive a structured explanation of whether the image may be misleadingly framed.',
    icon: (
      <svg
        width="20"
        height="20"
        viewBox="0 0 20 20"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.25"
        aria-hidden="true"
      >
        <circle cx="10" cy="10" r="8" />
        <path d="M6.5 10.5l2.5 2.5 4.5-5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
];

export default function HowItWorks() {
  return (
    <section
      id="how-it-works"
      className="px-6 py-24 md:py-32 border-t border-white/[0.05]"
      aria-labelledby="how-it-works-title"
    >
      <div className="max-w-5xl mx-auto">
        <SectionHeader
          eyebrow="Process"
          title="How it works"
          id="how-it-works-title"
        />

        <div className="grid md:grid-cols-3 gap-px bg-white/[0.05] rounded-2xl overflow-hidden">
          {STEPS.map((step) => (
            <div
              key={step.number}
              className="group bg-navy px-8 py-10 flex flex-col hover:bg-white/[0.02] transition-colors duration-300"
            >
              <span className="text-[10px] font-medium tracking-[0.18em] text-blue-muted/25 mb-7 block">
                {step.number}
              </span>

              <div className="w-10 h-10 border border-white/[0.08] rounded-xl flex items-center justify-center text-pale-blue/50 mb-7 group-hover:border-pale-blue/20 group-hover:text-pale-blue/75 transition-all duration-300">
                {step.icon}
              </div>

              <h3 className="text-[14px] font-medium text-white mb-2.5">{step.title}</h3>
              <p className="text-[13px] font-light text-blue-muted/65 leading-relaxed">
                {step.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
