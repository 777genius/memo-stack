class CostRates {
  // Match backend python defaults for Anthropic (per 1M tokens)
  static const double inputPerMTokensUsd = 3.0;
  static const double outputPerMTokensUsd = 15.0;

  static double inputUsdFor(int tokens) => (tokens / 1e6) * inputPerMTokensUsd;
  static double outputUsdFor(int tokens) =>
      (tokens / 1e6) * outputPerMTokensUsd;
}
