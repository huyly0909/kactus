import {
  LogOut,
  User,
  Settings,
  ChevronRight,
  Bug,
  Menu,
  ArrowLeft,
  Sun,
  Moon,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { useAuth } from '@/hooks/useAuth';
import { useBreadcrumb } from '@/layouts/components/useBreadcrumb';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { useDebugMode } from '@/hooks/useDebugMode';
import { useDebugStore } from '@/store/debugStore';
import { useNavStore } from '@/store/navStore';
import { useThemeStore } from '@/store/themeStore';

export function TopHeader() {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const crumbs = useBreadcrumb();
  const debug = useDebugMode();
  const toggleDebug = useDebugStore((s) => s.toggle);
  const toggleNav = useNavStore((s) => s.toggle);
  const mode = useThemeStore((s) => s.mode);
  const setMode = useThemeStore((s) => s.setMode);
  const navigate = useNavigate();
  // The data router stamps its entry index into history.state — idx 0 means
  // there is nothing to go back to. Recomputed each render (breadcrumb →
  // useLocation re-renders us on navigation).
  const canGoBack = (window.history.state?.idx ?? 0) > 0;

  const handleLogout = async () => {
    await logout();
    window.location.href = '/login';
  };

  return (
    <header className="h-14 flex items-center justify-between px-4 md:px-6 border-b border-border/40 bg-background/50 backdrop-blur-xl sticky top-0 z-30 transition-colors">
      <Button
        variant="ghost"
        size="icon"
        className="shrink-0 mr-1"
        aria-label={t('layout.go_back')}
        disabled={!canGoBack}
        onClick={() => navigate(-1)}
      >
        <ArrowLeft className="h-[18px] w-[18px]" />
      </Button>
      {/* Hamburger — opens the mobile nav drawer; hidden once the persistent
          sidebar shows at md. */}
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden shrink-0 mr-1"
        aria-label={t('layout.open_menu')}
        onClick={toggleNav}
      >
        <Menu className="h-[18px] w-[18px]" />
      </Button>
      {/* Below md only the last crumb renders; ancestors return at md. */}
      <nav aria-label="Breadcrumb" className="flex items-center min-w-0 flex-1">
        <ol className="flex items-center gap-1 text-sm min-w-0">
          {crumbs.map((c, i) => {
            const isLast = i === crumbs.length - 1;
            return (
              <li
                key={`${c.label}-${i}`}
                className={cn('items-center gap-1 min-w-0', isLast ? 'flex' : 'hidden md:flex')}
              >
                {i > 0 && (
                  <ChevronRight
                    className="hidden md:block w-3.5 h-3.5 text-muted-foreground/60 shrink-0"
                    aria-hidden
                  />
                )}
                {c.to && !isLast ? (
                  <Link
                    to={c.to}
                    className="text-muted-foreground hover:text-foreground transition-colors truncate"
                  >
                    {c.label}
                  </Link>
                ) : (
                  <span
                    className={cn(
                      'truncate',
                      isLast ? 'text-foreground font-semibold' : 'text-muted-foreground',
                    )}
                  >
                    {c.label}
                  </span>
                )}
              </li>
            );
          })}
        </ol>
      </nav>

      <div className="flex items-center gap-1.5">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              aria-label={t('layout.toggle_theme')}
              onClick={() => setMode(mode === 'dark' ? 'light' : 'dark')}
            >
              {mode === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom">
            <p className="text-xs">{t('layout.toggle_theme')}</p>
          </TooltipContent>
        </Tooltip>

        {debug && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                id="debug-mode-toggle"
                variant="ghost"
                size="icon"
                className="relative text-debug hover:text-debug/80 hover:bg-debug/10 transition-all duration-200"
                onClick={toggleDebug}
              >
                <Bug size={18} />
                <span className="absolute top-1.5 right-1.5 size-2 rounded-full bg-debug ring-2 ring-background animate-pulse" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <p className="text-xs">
                {t('common.debug_mode')}:{' '}
                <span className="font-semibold">{t('common.debug_mode_on')}</span>
              </p>
            </TooltipContent>
          </Tooltip>
        )}

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            {/* icon-lg, not icon: Avatar is size-8 and would exactly fill an
                icon button, leaving no inset for the hover ring. */}
            <Button variant="ghost" size="icon-lg">
              <Avatar>
                <AvatarFallback>
                  {user?.name ? user.name.charAt(0).toUpperCase() : <User size={14} />}
                </AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56 mt-1">
            <DropdownMenuGroup>
              <DropdownMenuLabel className="font-normal">
                <div className="flex flex-col space-y-1">
                  <p className="text-sm font-medium leading-none">
                    {user?.name || t('layout.account')}
                  </p>
                  <p className="text-xs leading-none text-muted-foreground">
                    {user?.email || t('layout.no_email')}
                  </p>
                </div>
              </DropdownMenuLabel>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild className="cursor-pointer mb-1">
              <Link to="/settings/profile">
                <Settings className="h-4 w-4 text-muted-foreground" />
                <span>{t('settings.title')}</span>
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={handleLogout}
              className="text-destructive focus:bg-destructive/10 focus:text-destructive cursor-pointer dark:focus:bg-destructive/20"
            >
              <LogOut className="h-4 w-4" />
              <span>{t('auth.logout')}</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
