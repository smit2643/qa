'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  LayoutDashboard,
  FolderKanban,
  Settings,
  Zap,
  ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const navItems = [
  {
    label: 'Dashboard',
    href: '/dashboard',
    icon: LayoutDashboard,
  },
  {
    label: 'Projects',
    href: '/projects',
    icon: FolderKanban,
  },
  {
    label: 'Settings',
    href: '/settings',
    icon: Settings,
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-60 flex-col border-r border-white/[0.06] bg-[#0a0a0a]">
      {/* Logo */}
      <div className="flex h-16 items-center gap-2.5 border-b border-white/[0.06] px-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-600">
          <Zap className="h-4 w-4 text-white" />
        </div>
        <span className="text-[15px] font-semibold tracking-tight text-white">
          BugForge
        </span>
        <span className="ml-1 rounded-full bg-violet-600/20 px-1.5 py-0.5 text-[10px] font-medium text-violet-300">
          BETA
        </span>
      </div>

      {/* Nav */}
      <nav className="flex flex-1 flex-col gap-1 p-3">
        {navItems.map((item) => {
          const isActive =
            pathname === item.href || pathname.startsWith(item.href + '/');
          const Icon = item.icon;

          return (
            <Link key={item.href} href={item.href}>
              <motion.div
                whileHover={{ x: 2 }}
                transition={{ duration: 0.15 }}
                className={cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-violet-600/15 text-violet-300'
                    : 'text-gray-400 hover:bg-white/[0.04] hover:text-white'
                )}
              >
                <Icon className="h-4 w-4 flex-shrink-0" />
                <span>{item.label}</span>
                {isActive && (
                  <ChevronRight className="ml-auto h-3 w-3 text-violet-400" />
                )}
              </motion.div>
            </Link>
          );
        })}
      </nav>

      {/* Bottom info */}
      <div className="border-t border-white/[0.06] p-3">
        <div className="rounded-lg bg-violet-600/10 p-3">
          <p className="text-xs font-medium text-violet-300">AI-Powered Testing</p>
          <p className="mt-0.5 text-[11px] text-gray-500">
            Describe tests in plain English
          </p>
        </div>
      </div>
    </aside>
  );
}
