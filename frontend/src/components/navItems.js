import {
  AlertTriangle, BarChart2, FileCheck, Gauge, Network, Scale, Upload, UserCheck, Zap,
} from 'lucide-react';

// One name per page: the same label appears in the sidebar, the phone tabs and the page title.
export const NAV_SECTIONS = [
  {
    label: 'Intelligence',
    items: [
      { path: '/',        label: 'Alerts',  icon: AlertTriangle, end: true },
      { path: '/queue',   label: 'Triage',  icon: Zap },
      { path: '/network', label: 'Network', icon: Network },
    ],
  },
  {
    label: 'Operations',
    items: [
      { path: '/complaints',      label: 'Fraud complaints', icon: Scale },
      { path: '/analytics',       label: 'ROI analytics',    icon: BarChart2 },
      { path: '/compliance',      label: 'Compliance',       icon: FileCheck },
      { path: '/risk-operations', label: 'Customer risk',    icon: UserCheck },
      { path: '/data-import',     label: 'Data import',      icon: Upload },
      { path: '/benchmarks',      label: 'Model benchmarks', icon: Gauge },
    ],
  },
];

export const isActivePath = (item, pathname) =>
  item.end ? pathname === item.path : pathname.startsWith(item.path);
