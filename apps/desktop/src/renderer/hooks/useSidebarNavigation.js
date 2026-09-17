import { useCallback, useEffect, useState } from "react";

const SIDEBAR_STORAGE_KEY = "interview-agent-sidebar-open";
const COMPACT_VIEWPORT_QUERY = "(max-width: 960px)";

function readDesktopPreference() {
  try {
    return window.localStorage.getItem(SIDEBAR_STORAGE_KEY) !== "0";
  } catch {
    return true;
  }
}

function isCompactViewport() {
  return window.matchMedia?.(COMPACT_VIEWPORT_QUERY).matches ?? false;
}

export function useSidebarNavigation() {
  const [compact, setCompact] = useState(isCompactViewport);
  const [open, setOpen] = useState(() => (
    isCompactViewport() ? false : readDesktopPreference()
  ));

  useEffect(() => {
    const media = window.matchMedia(COMPACT_VIEWPORT_QUERY);
    const handleChange = ({ matches }) => {
      setCompact(matches);
      setOpen(matches ? false : readDesktopPreference());
    };

    handleChange(media);
    media.addEventListener("change", handleChange);
    return () => media.removeEventListener("change", handleChange);
  }, []);

  useEffect(() => {
    if (compact) return;
    try {
      window.localStorage.setItem(SIDEBAR_STORAGE_KEY, open ? "1" : "0");
    } catch {
      // A blocked storage API should not prevent navigation.
    }
  }, [compact, open]);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "b") {
        event.preventDefault();
        setOpen((value) => !value);
      } else if (event.key === "Escape" && compact && open) {
        event.preventDefault();
        setOpen(false);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [compact, open]);

  useEffect(() => {
    if (!compact || !open) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.requestAnimationFrame(() => {
      document.querySelector("#app-sidebar .sidebar-collapse-btn")?.focus();
    });
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [compact, open]);

  return {
    compact,
    open,
    openSidebar: useCallback(() => setOpen(true), []),
    closeSidebar: useCallback(() => setOpen(false), []),
    closeAfterNavigation: useCallback(() => {
      if (isCompactViewport()) setOpen(false);
    }, [])
  };
}
