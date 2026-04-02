'use client';

import { useAuthStore } from '@/store/auth';
import { AppLayout } from '@/components/layout/AppLayout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { User, Shield, Bell } from 'lucide-react';

export default function SettingsPage() {
  const { user } = useAuthStore();

  return (
    <AppLayout title="Settings">
      <div className="mx-auto max-w-2xl space-y-6">
        <div>
          <h2 className="text-xl font-semibold text-white">Settings</h2>
          <p className="mt-0.5 text-sm text-gray-500">
            Manage your account and preferences
          </p>
        </div>

        {/* Profile */}
        <Card className="border-white/[0.06]">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base text-white">
              <User className="h-4 w-4 text-violet-400" />
              Profile
            </CardTitle>
            <CardDescription>Your account information</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-gray-300">Full Name</Label>
              <Input
                value={user?.name ?? ''}
                readOnly
                className="border-white/10 bg-white/[0.04] text-white"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-300">Email</Label>
              <Input
                value={user?.email ?? ''}
                readOnly
                className="border-white/10 bg-white/[0.04] text-white"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-300">User ID</Label>
              <Input
                value={user?.id ?? ''}
                readOnly
                className="border-white/10 bg-white/[0.04] font-mono text-xs text-gray-500"
              />
            </div>
          </CardContent>
        </Card>

        {/* Security */}
        <Card className="border-white/[0.06]">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base text-white">
              <Shield className="h-4 w-4 text-violet-400" />
              Security
            </CardTitle>
            <CardDescription>Authentication and security settings</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between rounded-lg border border-white/[0.06] p-3">
              <div>
                <p className="text-sm font-medium text-white">Password</p>
                <p className="text-xs text-gray-500">Last changed: Unknown</p>
              </div>
              <Badge variant="outline">Active</Badge>
            </div>
            <div className="flex items-center justify-between rounded-lg border border-white/[0.06] p-3">
              <div>
                <p className="text-sm font-medium text-white">Two-Factor Authentication</p>
                <p className="text-xs text-gray-500">Not configured</p>
              </div>
              <Badge variant="warning">Disabled</Badge>
            </div>
          </CardContent>
        </Card>

        {/* Notifications */}
        <Card className="border-white/[0.06]">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base text-white">
              <Bell className="h-4 w-4 text-violet-400" />
              Notifications
            </CardTitle>
            <CardDescription>Notification preferences (coming soon)</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4 text-center">
              <p className="text-sm text-gray-500">
                Notification settings will be available in a future update.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}
