const MOCK_RESULT = {
  imageUrl: 'https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=900&q=80',
  imageAlt: 'Aerial photograph showing smoke haze over a landscape — extracted from social media post',
  contextRisk: 'Medium',
  confidence: 78,
  verdict: 'This image may be presented without sufficient original context.',
  analysis:
    'The visual content appears to match a real photograph, but the surrounding post language may suggest a different time, place, or event than the image originally represented. Cross-referencing with known image databases indicates this image has appeared in multiple unrelated contexts over the past 36 months. The caption framing does not align with verifiable metadata associated with the image.',
  signals: [
    'Image context differs from caption framing',
    'Original source not clearly referenced',
    'Visual metadata unavailable',
    'Further verification recommended',
  ],
  nextSteps: [
    'Check original publication date',
    'Compare against trusted news sources',
    'Look for earlier appearances of the image',
  ],
  metadata: {
    platform: 'Social Media',
    analysisTime: '1.2s',
    imageResolution: '1280 × 720',
    sourceVerified: false,
  },
};

/**
 * Analyze a social media post URL for image context.
 *
 * TODO: Replace the mock implementation with a real API call to the Python backend.
 *
 * @param {string} url - The public social media post URL to analyze
 * @returns {Promise<Object>} Analysis result
 *
 * Expected backend endpoint: POST /api/analyze
 * Request body: { url: string }
 * Response shape:
 * {
 *   imageUrl: string,           // Direct URL to the extracted image
 *   imageAlt: string,           // Accessibility description
 *   contextRisk: 'Low' | 'Medium' | 'High',
 *   confidence: number,         // 0–100 percentage
 *   verdict: string,            // One-sentence conclusion
 *   analysis: string,           // Full analysis paragraph
 *   signals: string[],          // Key contextual signals detected
 *   nextSteps: string[],        // Recommended verification actions
 *   metadata: {
 *     platform: string,
 *     analysisTime: string,
 *     imageResolution: string,
 *     sourceVerified: boolean,
 *   }
 * }
 */
export async function analyzePostUrl(url) {
  // Simulate network + processing latency
  await new Promise((resolve) => setTimeout(resolve, 1500));

  // TODO: Replace with actual API call:
  // const response = await fetch('/api/analyze', {
  //   method: 'POST',
  //   headers: { 'Content-Type': 'application/json' },
  //   body: JSON.stringify({ url }),
  // });
  // if (!response.ok) throw new Error(`Analysis failed: ${response.statusText}`);
  // return response.json();

  return MOCK_RESULT;
}
