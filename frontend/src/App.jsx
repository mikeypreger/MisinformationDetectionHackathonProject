import { useState, useRef } from 'react';
import Header from './components/Header';
import Hero from './components/Hero';
import ResultCard from './components/ResultCard';
import HowItWorks from './components/HowItWorks';
import About from './components/About';
import UseCases from './components/UseCases';
import FAQ from './components/FAQ';
import Footer from './components/Footer';
import { analyzePostUrl } from './api/analyze';

export default function App() {
  const [analysisState, setAnalysisState] = useState('idle'); // 'idle' | 'loading' | 'result' | 'error'
  const [analysisResult, setAnalysisResult] = useState(null);
  const [analyzedUrl, setAnalyzedUrl] = useState('');
  const resultRef = useRef(null);

  const handleAnalyze = async (url) => {
    setAnalyzedUrl(url);
    setAnalysisState('loading');
    setAnalysisResult(null);

    try {
      const result = await analyzePostUrl(url);
      setAnalysisResult(result);
      setAnalysisState('result');
      setTimeout(() => {
        resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 120);
    } catch {
      setAnalysisState('error');
    }
  };

  const handleReset = () => {
    setAnalysisState('idle');
    setAnalysisResult(null);
    setAnalyzedUrl('');
  };

  return (
    <div className="min-h-screen bg-navy text-white font-sans">
      <Header />
      <main>
        <Hero
          onAnalyze={handleAnalyze}
          analysisState={analysisState}
          onReset={handleReset}
        />

        <div ref={resultRef}>
          {analysisState === 'result' && analysisResult && (
            <ResultCard result={analysisResult} url={analyzedUrl} onReset={handleReset} />
          )}
        </div>

        <HowItWorks />
        <About />
        <UseCases />
        <FAQ />
      </main>
      <Footer />
    </div>
  );
}
