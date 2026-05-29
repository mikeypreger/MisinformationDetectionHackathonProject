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

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {USE_CASES.map((useCase) => (
            <div
              key={useCase.title}
              className="group border border-white/[0.07] rounded-xl p-6 bg-white/[0.02] hover:bg-white/[0.04] hover:border-white/[0.11] transition-all duration-300 cursor-default"
            >
              <span
                className="text-[18px] text-pale-blue/30 group-hover:text-pale-blue/50 transition-colors duration-300 mb-4 block"
                aria-hidden="true"
              >
                {useCase.symbol}
              </span>
              <h3 className="text-[13px] font-medium text-white mb-2">{useCase.title}</h3>
              <p className="text-[13px] font-light text-blue-muted/60 leading-relaxed">
                {useCase.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
