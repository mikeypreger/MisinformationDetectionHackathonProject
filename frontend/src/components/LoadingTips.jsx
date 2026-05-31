import { useState, useEffect } from 'react';

const TIPS = [
  "Check the source — is the outlet known, reputable, and clearly identified?",
  "Read beyond the headline. Headlines are written to provoke, not inform.",
  "Images are the most recycled form of misinformation. Old photos are constantly reposted with new captions.",
  "Do a reverse image search on any image that seems dramatic or hard to believe.",
  "Check if multiple independent, credible outlets are reporting the same story.",
  "Look at the date. \"Breaking news\" is sometimes years-old content reshared to fit today's narrative.",
  "Check your emotions. If content makes you instantly outraged or elated, pause before sharing.",
  "Look for an author. Anonymous posts with no byline are a major red flag.",
  "Verify the location. Captions often claim a photo was taken somewhere it was not.",
  "Look at the account history. New accounts spreading viral content are often inauthentic.",
  "Beware of statistics without a cited source. Numbers can be invented just as easily as words.",
  "Satire sites intentionally publish fake stories. Always check if the source is known for satire.",
  "Check the URL closely. Misinformation sites mimic real ones — e.g. ABCnews.com.co is not ABC News.",
  "Cross-check with a fact-checker: Snopes, FactCheck.org, or PolitiFact.",
  "A quote in an image can be edited. Find the original speech or interview to verify it.",
  "Ask: who benefits from you believing this? Follow the incentive.",
  "Widely shared does not mean true. Misinformation spreads faster than corrections.",
  "Cropping an image can completely change its meaning. Look for full, uncropped versions.",
  "Out-of-context images are not always malicious — but they are always misleading.",
  "If the content perfectly confirms what you already believe, be extra skeptical.",
];

export default function LoadingTips() {
  const [index, setIndex] = useState(() => Math.floor(Math.random() * TIPS.length));
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const interval = setInterval(() => {
      setVisible(false);
      setTimeout(() => {
        setIndex((i) => (i + 1) % TIPS.length);
        setVisible(true);
      }, 400);
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="mt-10 flex flex-col items-center gap-5 animate-fade-in">
      {/* Animated dots */}
      <div className="flex items-center gap-1.5" aria-hidden="true">
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="w-1.5 h-1.5 rounded-full bg-accent/60 animate-bounce"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </div>

      {/* Tip card */}
      <div className="w-full max-w-xl mx-auto rounded-xl border border-white/[0.07] bg-white/[0.03] px-6 py-4">
        <p
          className="text-[11px] font-semibold tracking-[0.14em] uppercase text-accent/70 mb-2"
          aria-hidden="true"
        >
          Did you know?
        </p>
        <p
          className="text-[13px] text-blue-muted/80 font-light leading-relaxed transition-opacity duration-300"
          style={{ opacity: visible ? 1 : 0 }}
          aria-live="polite"
          aria-label={`Tip: ${TIPS[index]}`}
        >
          {TIPS[index]}
        </p>
      </div>

      <p className="text-[11px] text-blue-muted/40 font-light tracking-wide">
        Analyzing image context — this takes about 30 seconds…
      </p>
    </div>
  );
}
