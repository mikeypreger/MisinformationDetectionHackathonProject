import { useState, useRef } from 'react';
import LoadingTips from './LoadingTips';

function isValidUrl(str) {
  try {
    const url = new URL(str.trim());
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

export default function Hero({ onAnalyze, analysisState, analysisError, onReset }) {
  const [inputUrl, setInputUrl] = useState('');
  const [inputError, setInputError] = useState('');
  const [focused, setFocused] = useState(false);
  const inputRef = useRef(null);

  const isLoading = analysisState === 'loading';
  const isResult = analysisState === 'result';
  const isError = analysisState === 'error';

  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmed = inputUrl.trim();

    if (!trimmed) {
      setInputError('Please enter a URL to analyze.');
      inputRef.current?.focus();
      return;
    }
    if (!isValidUrl(trimmed)) {
      setInputError("This doesn't look like a valid URL. Please include https://");
      inputRef.current?.focus();
      return;
    }

    setInputError('');
    onAnalyze(trimmed);
  };

  const handleChange = (e) => {
    setInputUrl(e.target.value);
    if (inputError) setInputError('');
  };

  const handleReset = () => {
    setInputUrl('');
    setInputError('');
    onReset();
  };

  return (
    <section
      id="hero"
      className="relative flex flex-col items-center justify-center min-h-screen px-6 pt-20 pb-16"
      aria-labelledby="hero-headline"
    >
      {/* Ambient glow */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden" aria-hidden="true">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[650px] bg-accent/[0.08] rounded-full blur-[130px]" />
        <div className="absolute top-1/4 right-1/4 w-[350px] h-[350px] bg-highlight/[0.04] rounded-full blur-[90px]" />
        <div className="absolute bottom-1/4 left-1/5 w-[250px] h-[250px] bg-accent/[0.04] rounded-full blur-[80px]" />
      </div>

      <div className="relative w-full max-w-3xl mx-auto text-center">
        {/* Eyebrow */}
        <div className="inline-flex items-center mb-10 animate-fade-in">
          <span className="inline-block text-[11px] font-semibold tracking-[0.18em] uppercase text-accent/80 border border-accent/25 rounded-full px-4 py-1.5 bg-accent/[0.06]">
            AI-Powered Misinformation Detection
          </span>
        </div>

        {/* Headline */}
        <h1
          id="hero-headline"
          className="font-display text-[44px] sm:text-[58px] md:text-[70px] font-bold leading-[1.02] tracking-[-0.03em] text-white mb-6 text-balance animate-fade-up"
        >
          See when an image is
          <br />
          <span className="text-highlight">missing its context.</span>
        </h1>

        {/* Subheadline */}
        <p
          className="text-[16px] sm:text-[18px] font-light text-blue-muted max-w-[520px] mx-auto mb-14 leading-relaxed animate-fade-up"
          style={{ animationDelay: '0.08s' }}
        >
          Paste a social media post URL and get a clear visual-context analysis designed to help
          identify misleading image use.
        </p>

        {/* Form — hidden in result state */}
        {!isResult && (
          <form
            onSubmit={handleSubmit}
            className="w-full max-w-2xl mx-auto animate-fade-up"
            style={{ animationDelay: '0.14s' }}
            noValidate
            aria-label="URL analysis form"
          >
            <div
              className={`flex items-center gap-2 p-1.5 rounded-xl border transition-all duration-300 ${
                inputError
                  ? 'border-red-400/35 bg-white/[0.025]'
                  : focused
                  ? 'border-accent/35 bg-white/[0.055] shadow-[0_0_0_5px_rgba(230,57,70,0.06)]'
                  : 'border-white/[0.08] bg-white/[0.025] hover:border-white/[0.12]'
              }`}
            >
              <label htmlFor="url-input" className="sr-only">
                Social media post URL
              </label>
              <input
                id="url-input"
                ref={inputRef}
                type="url"
                value={inputUrl}
                onChange={handleChange}
                onFocus={() => setFocused(true)}
                onBlur={() => setFocused(false)}
                placeholder="Paste a social media post URL…"
                disabled={isLoading}
                autoComplete="off"
                autoCorrect="off"
                autoCapitalize="off"
                spellCheck={false}
                className="flex-1 min-w-0 bg-transparent text-white placeholder-blue-muted/45 text-sm font-light px-3 py-2.5 outline-none disabled:opacity-50 transition-opacity"
                aria-describedby={inputError ? 'url-error' : 'url-hint'}
                aria-invalid={!!inputError}
              />
              <button
                type="submit"
                disabled={isLoading}
                className="flex-shrink-0 bg-accent hover:bg-accent-hover disabled:opacity-55 text-white text-sm font-semibold px-5 py-2.5 rounded-[8px] transition-all duration-200 shadow-[0_2px_14px_rgba(230,57,70,0.3)] hover:shadow-[0_4px_20px_rgba(230,57,70,0.5)] focus:outline-none focus:ring-2 focus:ring-accent/40 disabled:cursor-not-allowed whitespace-nowrap"
                aria-label={isLoading ? 'Analyzing…' : 'Analyze post'}
              >
                {isLoading ? (
                  <span className="flex items-center gap-2">
                    <SpinnerIcon />
                    Analyzing
                  </span>
                ) : (
                  'Analyze'
                )}
              </button>
            </div>

            {/* Inline input error */}
            {inputError && (
              <p
                id="url-error"
                role="alert"
                className="mt-3 text-[13px] text-red-400/85 text-left px-1 flex items-center gap-1.5"
              >
                <AlertIcon />
                {inputError}
              </p>
            )}

            {/* Backend error */}
            {isError && !inputError && (
              <p
                role="alert"
                className="mt-3 text-[13px] text-red-400/85 text-center flex items-center justify-center gap-1.5"
              >
                <AlertIcon />
                {analysisError || 'Analysis failed. Please check the URL and try again.'}
              </p>
            )}

            {/* Loading state indicator */}
            {isLoading && <LoadingTips />}

            {/* Hint text */}
            {!inputError && !isLoading && !isError && (
              <p id="url-hint" className="mt-3 text-[12px] text-blue-muted/45 text-center">
                Supports public posts from Instagram, Twitter, TikTok, Facebook, and Reddit.
              </p>
            )}
          </form>
        )}

        {/* Reset button (result state) */}
        {isResult && (
          <button
            onClick={handleReset}
            className="inline-flex items-center gap-2 text-[13px] font-light text-blue-muted/65 hover:text-white transition-colors duration-200 group animate-fade-in"
            aria-label="Analyze another post"
          >
            <svg
              width="13"
              height="13"
              viewBox="0 0 13 13"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="group-hover:-rotate-45 transition-transform duration-300"
              aria-hidden="true"
            >
              <path d="M1.5 6.5a5 5 0 1 0 5-5" />
              <path d="M1.5 2v4.5H6" />
            </svg>
            Analyze another post
          </button>
        )}
      </div>

      {/* Scroll hint */}
      {analysisState === 'idle' && (
        <div
          className="absolute bottom-10 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 opacity-20 animate-fade-in"
          style={{ animationDelay: '1s' }}
          aria-hidden="true"
        >
          <svg
            className="animate-bounce w-4 h-4 text-accent"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      )}
    </section>
  );
}

function SpinnerIcon() {
  return (
    <svg
      className="animate-spin w-3.5 h-3.5"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" className="opacity-20" />
      <path
        d="M22 12a10 10 0 0 0-10-10"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}

function AlertIcon() {
  return (
    <svg
      width="13"
      height="13"
      viewBox="0 0 14 14"
      fill="currentColor"
      className="flex-shrink-0"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M7 1a6 6 0 100 12A6 6 0 007 1zm-.75 3.5a.75.75 0 011.5 0v3a.75.75 0 01-1.5 0v-3zm.75 5.5a.875.875 0 100-1.75.875.875 0 000 1.75z"
      />
    </svg>
  );
}
