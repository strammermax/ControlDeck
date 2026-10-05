export const navigation = [
  { id: "dashboard", label: "Dashboard" },
  { id: "virtual-apps", label: "Virtual Apps" },
  { id: "bookmarks", label: "Bookmarks" },
  { id: "proxmox", label: "Proxmox", children: [
    ["proxmox", "Overzicht"], ["proxmox/nodes", "Nodes"], ["proxmox/vms", "Virtual Machines"],
    ["proxmox/containers", "Containers"], ["proxmox/storage", "Storage"], ["files", "Files"],
    ["network", "Network"], ["monitoring", "Monitoring"],
  ] },
  { id: "media", label: "Media" },
  { id: "terminal", label: "Terminal" },
  { id: "admin", label: "Admin", children: [
    ["admin", "Instellingen"], ["admin/modules", "Modules"], ["admin/providers", "Providers"], ["admin/users", "Gebruikers"],
  ] },
];
export const destinations = navigation.flatMap(item => [{ id: item.id, label: item.label }, ...(item.children ?? []).map(([id, label]) => ({ id, label }))]);
