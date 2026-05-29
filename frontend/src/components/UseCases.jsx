import SectionHeader from './SectionHeader';

const USE_CASES = [
  {
    title: 'Journalism & fact-checking',
    description:
      'Support editorial verification workflows with structured image context analysis before publication.',
    symbol: '◎',
  },
  {
    title: 'Academic research',
    description:
      'Trace the provenance and reuse of images across social platforms for systematic research.',
    symbol: '◫',
  },
  {
    title: 'Media literacy',
    description:
      'Educate readers and students on recognizing and understanding misleadingly framed visual content.',
    symbol: '◈',
  },
  {
    title: 'Social media monitoring',
    description:
      'Detect images used in contexts that diverge significantly from their original meaning.',
    symbol: '◐',
  },
  {
    title: 'Public communication teams',
    description:
      'Verify imagery accuracy before publishing to protect organizational credibility and trust.',
    symbol: '◻',
  },
];

export default function UseCases() {
  return (
    <section
      id="use-cases"
      className="px-6 py-24 md:py-32 border-t border-white/[0.05]"
      aria-labelledby="use-cases-title"
    >
      <div className="max-w-5xl mx-auto">
        <SectionHeader
          eyebrow="Applications"
          title="Use cases"
          id="use-cases-title"
          subtitle="miss information is built for anyone who needs to move beyond surface-level image sharing and examine what is really being communicated."
        />

        <div className="relative">
          {/* vertical center line */}
          <div className="absolute left-1/2 top-0 bottom-0 w-px bg-white/10 -translate-x-1/2" />

          {USE_CASES.map((useCase, index) => {
            const isLeft = index % 2 === 0;
            return (
              <div
                key={useCase.title}
                className={`group flex items-center mb-10 last:mb-0 ${isLeft ? 'flex-row' : 'flex-row-reverse'}`}
              >
                {/* content */}
                <div
                  className={`w-[45%] cursor-default transition-transform duration-300 ease-out group-hover:scale-[1.04] ${isLeft ? 'text-right pr-8' : 'text-left pl-8'}`}
                >
                  <span
                    className="text-[18px] text-pale-blue/30 group-hover:text-pale-blue/50 transition-colors duration-300 mb-2 block"
                    aria-hidden="true"
                  >
                    {useCase.symbol}
                  </span>
                  <h3 className="text-[13px] font-medium text-white mb-1 leading-snug">
                    {useCase.title}
                  </h3>
                  <p className="text-[13px] font-light text-blue-muted/60 leading-relaxed">
                    {useCase.description}
                  </p>
                </div>

                {/* dot on the line */}
                <div className="w-[10%] flex justify-center z-10">
                  <div className="w-2.5 h-2.5 rounded-full border border-white/20 bg-white/[0.06] group-hover:bg-pale-blue/30 group-hover:border-pale-blue/40 transition-all duration-300" />
                </div>

                {/* empty side */}
                <div className="w-[45%]" />
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
