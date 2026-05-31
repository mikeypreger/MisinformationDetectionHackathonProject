export default function SectionHeader({ eyebrow, title, id, subtitle }) {
  return (
    <div className="mb-12">
      {eyebrow && (
        <p className="text-[10px] font-semibold tracking-[0.18em] uppercase text-accent/70 mb-3">
          {eyebrow}
        </p>
      )}
      <h2
        id={id}
        className="font-display text-[28px] sm:text-[34px] font-bold text-white leading-tight tracking-[-0.02em]"
      >
        {title}
      </h2>
      {subtitle && (
        <p className="mt-4 text-[14px] font-light text-blue-muted/65 max-w-xl leading-relaxed">
          {subtitle}
        </p>
      )}
    </div>
  );
}
