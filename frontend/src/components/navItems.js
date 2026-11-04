import {
  AlertTriangle, BarChart2, Boxes, FileCheck, Gauge, LayoutDashboard, Network, Radio, Scale, Undo2, Upload, UserCheck, Zap,
} from 'lucide-react';

import { EXTRA_PATHS, EXTRA_PAGES_ENABLED } from '../config/features';

// One name per page: the same label appears in the sidebar, the phone tabs and the page title.
const ALL_SECTIONS = [
  {
    label: 'Platform',
    items: [
      { path: '/command-center', label: 'Command center',    icon: LayoutDashboard },
      { path: '/modules',        label: 'Detection modules', icon: Boxes },
    ],
  },
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
      { path: '/live',           label: 'Live stream',      icon: Radio },
      { path: '/complaints',      label: 'Fraud complaints', icon: Scale },
      { path: '/returns',        label: 'Return fraud',     icon: Undo2 },
      { path: '/analytics',       label: 'ROI analytics',    icon: BarChart2 },
      { path: '/compliance',      label: 'Compliance',       icon: FileCheck },
      { path: '/risk-operations', label: 'Customer risk',    icon: UserCheck },
      { path: '/data-import',     label: 'Data import',      icon: Upload },
      { path: '/benchmarks',      label: 'Model benchmarks', icon: Gauge },
    ],
  },
];

export const NAV_SECTIONS = ALL_SECTIONS.map(section => ({
  ...section,
  items: section.items.filter(i => EXTRA_PAGES_ENABLED || !EXTRA_PATHS.includes(i.path)),
}));

export const isActivePath = (item, pathname) =>
  item.end ? pathname === item.path : pathname.startsWith(item.path);
