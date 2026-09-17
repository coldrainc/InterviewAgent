import { Loader2, RefreshCw } from "lucide-react";
import { useInfiniteScroll } from "../../hooks/useInfiniteScroll";

export function InfiniteScrollSentinel({ hasMore, loading, error, onLoadMore }) {
  const ref = useInfiniteScroll({ enabled: hasMore && !loading && !error, onLoadMore });
  if (!hasMore && !loading && !error) return null;
  return (
    <div ref={ref} className="infinite-scroll-sentinel" aria-live="polite">
      {loading && <><Loader2 size={15} className="spin" /> 正在加载更多…</>}
      {error && (
        <button type="button" className="btn-ghost-v3 small" onClick={onLoadMore}>
          <RefreshCw size={13} /> 加载失败，重试
        </button>
      )}
    </div>
  );
}
