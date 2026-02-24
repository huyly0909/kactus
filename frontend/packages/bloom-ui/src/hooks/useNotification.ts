import { useCallback } from 'react';
import { notifications } from '@mantine/notifications';

/**
 * Notification hook — provides both Mantine in-app toasts
 * and native Browser Notification API push notifications.
 */
export const useNotification = () => {
    /** Show an in-app toast using Mantine */
    const showToast = useCallback(
        (options: { title: string; message: string; color?: string }) => {
            notifications.show({
                title: options.title,
                message: options.message,
                color: options.color || 'blue',
                autoClose: 5000,
            });
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
