/**
 * Analyze a social media post URL for image context.
 *
 * @param {string} url - The public social media post URL to analyze
 * @param {boolean} simulationMode - Skip all API/network calls; use synthetic data
 * @returns {Promise<Object>} Analysis result matching ResultCard's expected shape
 */
export async function analyzePostUrl(url, simulationMode = false) {
  const response = await fetch('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, simulation_mode: simulationMode }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Analysis failed: ${response.statusText}`);
  }

  return response.json();
}
