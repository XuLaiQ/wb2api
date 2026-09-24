'use client';

import {useEffect, useState} from 'react';
import {LogOut, Users} from 'lucide-react';
import packageJson from '../../../package.json';
import {useAuth} from '@/lib/auth-context';
import {accountApi, systemApi} from '@/lib/api';
import {useT} from '@/lib/i18n/provider';
import {PageHeader} from '@/components/common/layout/PageHeader';
import {ConfirmDialog} from '@/components/common/layout/ConfirmDialog';
import {Avatar, AvatarFallback} from '@/components/ui/avatar';
import {Badge} from '@/components/ui/badge';
import {Button} from '@/components/ui/button';
import {Separator} from '@/components/ui/separator';

const BUILD_TIME = process.env.NEXT_PUBLIC_BUILD_TIME || '';

export default function ProfilePage() {
  const t = useT();
  const {me, logout} = useAuth();
  const [accountCount, setAccountCount] = useState<number | null>(null);
  const [runtimeVersion, setRuntimeVersion] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    accountApi.list().then((data) => { if (alive) setAccountCount(data.total); }).catch(() => { if (alive) setAccountCount(null); });
    systemApi.versions().then((v) => { if (alive && v?.manager) setRuntimeVersion(v.manager); }).catch(() => {});
    const refresh = () => accountApi.list().then((data) => { if (alive) setAccountCount(data.total); }).catch(() => {});
    window.addEventListener('workbuddy-manager:accounts-changed', refresh);
    return () => { alive = false; window.removeEventListener('workbuddy-manager:accounts-changed', refresh); };
  }, []);



  return (
    <div className="space-y-6">
      <PageHeader title={t('profile.title')} description={t('profile.desc')} />
      <div className="max-w-3xl">
        <section className="space-y-5 rounded-[24px] border border-border/70 bg-card p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex min-w-0 items-center gap-4">
              <Avatar className="size-14 rounded-2xl"><AvatarFallback className="bg-primary/10 text-base font-semibold text-primary">{me?.username?.slice(0, 2).toUpperCase() || 'U'}</AvatarFallback></Avatar>
              <div className="min-w-0">
                <h2 className="truncate text-lg font-semibold">{me?.username || '—'}</h2>
                <p className="text-sm text-muted-foreground">workbuddy2Api</p>
                {me && <Badge variant="secondary" className="mt-2 rounded-full">{me.role === 'admin' ? t('profile.roleAdmin') : t('profile.roleViewer')}</Badge>}
              </div>
            </div>
            <ConfirmDialog title={t('profile.logoutTitle')} description={t('profile.logoutDesc')} confirmText={t('profile.logout')} destructive onConfirm={logout} trigger={<Button variant="outline" className="rounded-full"><LogOut className="mr-2 size-4" />{t('profile.logout')}</Button>} />
          </div>
          <Separator />
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl bg-muted/70 p-4">
              <div className="flex items-center gap-2 text-sm font-medium"><Users className="size-4 text-primary" />{t('profile.managedAccounts')}</div>
              <div className="mt-2 text-2xl font-semibold tabular-nums">{accountCount ?? '—'}</div>
            </div>
            <div className="rounded-2xl bg-muted/70 p-4">
              <div className="text-sm font-medium">{t('profile.about')}</div>
              <div className="mt-2 text-sm font-semibold">{runtimeVersion ? `Version ${runtimeVersion}` : `Version ${packageJson.version}${t('profile.versionFallback')}`}</div>
              {BUILD_TIME && <div className="mt-1 text-xs text-muted-foreground">Build At {BUILD_TIME}</div>}
            </div>
          </div>
          <p className="text-sm leading-6 text-muted-foreground">{t('profile.aboutDesc')}</p>
        </section>

      </div>
    </div>
  );
}
