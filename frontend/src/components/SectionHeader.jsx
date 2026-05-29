export default function SectionHeader({ eyebrow, title, id, subtitle }) {
  return (
    <div className="mb-12">
      {eyebrow && (
        <p className="text-[10px] font-medium tracking-[0.16em] uppercase text-blue-muted/45 mb-3">
          {eyebrow}
        </p>
      )}
      <h2
        id={id}
        className="text-[26px] sm:text-[32px] font-light text-white leading-tight"
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
