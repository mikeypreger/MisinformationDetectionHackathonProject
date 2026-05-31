import { useState } from 'react';
import SectionHeader from './SectionHeader';

const FAQ_ITEMS = [
  {
    question: 'Does MISS INFORMATION decide what is true?',
    answer:
      'No. It provides contextual signals and analysis to support verification, not replace human judgment. The platform is a tool for researchers, journalists, and readers — not an arbiter of truth. All conclusions should be interpreted alongside other verification methods.',
  },
  {
    question: 'Can it analyze every social media post?',
    answer:
      'The frontend is prepared for public image-based posts. Backend support will define which platforms are supported. Initially, publicly accessible posts containing images will be prioritized. Private or restricted content cannot be analyzed.',
  },
  {
    question: "What does 'out of context' mean?",
    answer:
      "An image may be real but used with a misleading caption, wrong date, wrong location, or associated with an unrelated event. The platform looks for signals that the framing diverges from the image's original meaning or documented history.",
  },
  {
    question: 'Is this frontend connected to real analysis?',
    answer:
      'Not yet. This version includes mocked results and is designed to connect to a Python analysis pipeline. The UI, component structure, and API interface are all ready for backend integration. The mock results illustrate the intended output format.',
  },
  {
    question: 'Who is MISS INFORMATION designed for?',
    answer:
      'The platform is built for journalists, fact-checkers, researchers, media literacy educators, and anyone who needs to assess whether an image is being presented in its accurate original context. It is intentionally serious and analytical in tone.',
  },
];

function FAQItem({ item, isOpen, onToggle }) {
  return (
    <div className="border-b border-white/[0.06]">
      <button
        className="w-full flex items-center justify-between gap-6 py-5 text-left group focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/30 rounded"
        onClick={onToggle}
        aria-expanded={isOpen}
      >
        <span className="text-[14px] font-light text-white/85 group-hover:text-white transition-colors duration-200 leading-snug">
          {item.question}
        </span>
        <span
          className={`flex-shrink-0 w-6 h-6 border border-white/[0.1] rounded-full flex items-center justify-center text-blue-muted/50 transition-all duration-300 ${
            isOpen ? 'rotate-45 border-accent/30 text-accent/70' : ''
          }`}
          aria-hidden="true"
        >
          <svg
            width="10"
            height="10"
            viewBox="0 0 10 10"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          >
            <path d="M5 2v6M2 5h6" />
          </svg>
        </span>
      </button>

      <div
        className={`overflow-hidden transition-all duration-300 ease-in-out ${
          isOpen ? 'max-h-56 opacity-100 pb-5' : 'max-h-0 opacity-0'
        }`}
      >
        <p className="text-[13px] font-light text-blue-muted/68 leading-relaxed pr-10">
          {item.answer}
        </p>
      </div>
    </div>
  );
}

export default function FAQ() {
  const [openIndex, setOpenIndex] = useState(null);

  const handleToggle = (index) => {
    setOpenIndex((prev) => (prev === index ? null : index));
  };

  return (
    <section
      id="faq"
      className="px-6 py-24 md:py-32 border-t border-white/[0.05]"
      aria-labelledby="faq-title"
    >
      <div className="max-w-3xl mx-auto">
        <SectionHeader
          eyebrow="FAQ"
          title="Frequently asked questions"
          id="faq-title"
        />

        <div role="list">
          {FAQ_ITEMS.map((item, index) => (
            <FAQItem
              key={item.question}
              item={item}
              isOpen={openIndex === index}
              onToggle={() => handleToggle(index)}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
