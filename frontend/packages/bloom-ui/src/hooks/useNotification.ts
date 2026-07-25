import { useCallback } from 'react';
import { toast } from 'sonner';

/**
 * Notification hook — provides both in-app toasts (via `sonner`)
 * and native Browser Notification API push notifications.
 */
export const useNotification = () => {
  /** Show an in-app toast. `type` maps to sonner's success/error/warning/info. */
  const showToast = useCallback(
    (options: {
      title: string;
      message: string;
      type?: 'success' | 'error' | 'warning' | 'info';
    }) => {
      const fn =
        options.type === 'success'
          ? toast.success
          : options.type === 'error'
            ? toast.error
            : options.type === 'warning'
              ? toast.warning
              : toast.info;
      fn(options.title, { description: options.message, duration: 5000 });
    },
    [],
  );

  /** Send a native browser push notification */
  const sendBrowserNotification = useCallback(
    async (title: string, body: string, options?: NotificationOptions) => {
      if (!('Notification' in window)) {
        console.warn('Browser does not support notifications');
        return;
      }

      if (Notification.permission === 'default') {
        await Notification.requestPermission();
      }

      if (Notification.permission === 'granted') {
        new Notification(title, { body, icon: '/favicon.svg', ...options });
      }
    },
    [],
  );

  /** Request notification permission */
  const requestPermission = useCallback(async () => {
    if ('Notification' in window && Notification.permission === 'default') {
      return Notification.requestPermission();
    }
    return Notification.permission;
  }, []);

  return { showToast, sendBrowserNotification, requestPermission };
};
