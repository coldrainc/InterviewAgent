export function SidebarBackdrop({ open, onClose }) {
  if (!open) return null;

  return (
    <button
      type="button"
      className="sidebar-backdrop"
      onClick={onClose}
      aria-label="关闭主菜单"
      tabIndex={-1}
    />
  );
}
