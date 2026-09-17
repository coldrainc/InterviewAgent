import { useCallback, useEffect, useRef, useState } from "react";

function scrollParent(element) {
  let parent = element?.parentElement;
  while (parent) {
    const style = window.getComputedStyle(parent);
    if (/(auto|scroll)/u.test(`${style.overflowY} ${style.overflow}`)) return parent;
    parent = parent.parentElement;
  }
  return null;
}

export function useInfiniteScroll({ enabled, onLoadMore, root, rootMargin = "800px 0px" }) {
  const sentinelRef = useRef(null);
  const [target, setTarget] = useState(null);
  const loadRef = useRef(onLoadMore);
  loadRef.current = onLoadMore;

  useEffect(() => {
    if (!target || !enabled) return undefined;
    const observerRoot = root === undefined ? scrollParent(target) : root;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) loadRef.current?.();
      },
      { root: observerRoot, rootMargin, threshold: 0.01 }
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [enabled, root, rootMargin, target]);

  return useCallback((node) => {
    sentinelRef.current = node;
    setTarget(node);
  }, []);
}

export function mergeUniqueById(current, incoming) {
  const keyOf = (item) => String(item?.id || item?.user_id || item?.question_id || "");
  const seen = new Set(current.map(keyOf));
  return [...current, ...incoming.filter((item) => {
    const id = keyOf(item);
    if (!id || seen.has(id)) return false;
    seen.add(id);
    return true;
  })];
}
