export function shouldOpenEvidence({ sourceCount, conditionCount, compact, loading, manualChoice }) {
  return !compact && !loading && manualChoice !== false && (sourceCount > 0 || conditionCount > 0)
}
