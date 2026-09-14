/** Reusable inline loading indicator with a label. */
export function LoadingState({ label = "Loading..." }) {
  return (
    <div className="inline-state inline-state-loading" role="status">
      <div className="loading-spinner loading-spinner-sm" />
      <span>{label}</span>
    </div>
  );
}

/** Reusable inline error message with an optional retry action. */
export function ErrorState({ message, onRetry, retryLabel = "Retry" }) {
  return (
    <div className="inline-state inline-state-error" role="alert">
      <span>{message}</span>

      {onRetry && (
        <button type="button" className="btn btn-outline btn-sm" onClick={onRetry}>
          {retryLabel}
        </button>
      )}
    </div>
  );
}

/** Reusable empty-state block (icon + title + supporting text). */
export function EmptyState({ icon: Icon, title, message }) {
  return (
    <div className="empty-state">
      {Icon && <Icon size={26} />}
      <strong>{title}</strong>
      {message && <span>{message}</span>}
    </div>
  );
}
