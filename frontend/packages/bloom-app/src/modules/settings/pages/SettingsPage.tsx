import { type FC } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { ProfilePane } from '@modules/settings/components/ProfilePane';
import { AppearancePane } from '@modules/settings/components/AppearancePane';

const TABS = [
  { value: 'profile', labelKey: 'settings.profile' },
  { value: 'appearance', labelKey: 'settings.appearance' },
] as const;

export const SettingsPage: FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { tab } = useParams<{ tab: string }>();
  const active = TABS.some((x) => x.value === tab) ? (tab as string) : 'profile';

  return (
    <div className="mx-auto w-full max-w-3xl p-4 md:p-6">
      <h1 className="mb-4 text-2xl font-bold tracking-tight text-foreground">
        {t('settings.title')}
      </h1>
      <Tabs value={active} onValueChange={(v) => navigate(`/settings/${v}`)}>
        <TabsList className="mb-4">
          {TABS.map((tabDef) => (
            <TabsTrigger key={tabDef.value} value={tabDef.value}>
              {t(tabDef.labelKey)}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="profile">
          <ProfilePane />
        </TabsContent>
        <TabsContent value="appearance">
          <AppearancePane />
        </TabsContent>
      </Tabs>
    </div>
  );
};
