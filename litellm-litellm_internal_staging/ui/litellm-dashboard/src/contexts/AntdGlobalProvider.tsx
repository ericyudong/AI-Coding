"use client";

import React, { useEffect, useRef } from "react";
import { ConfigProvider, notification, message } from "antd";
import enUS from "antd/locale/en_US";
import zhCN from "antd/locale/zh_CN";
import dayjs from "dayjs";
import "dayjs/locale/zh-cn";
import { setNotificationInstance } from "@/components/molecules/notifications_manager";
import { setMessageInstance } from "@/components/molecules/message_manager";
import { useI18n } from "@/i18n";

export default function AntdGlobalProvider({ children }: { children: React.ReactNode }) {
  const { locale } = useI18n();
  const [notificationApi, notificationContextHolder] = notification.useNotification();
  const [messageApi, messageContextHolder] = message.useMessage();
  const initialized = useRef(false);

  useEffect(() => {
    if (!initialized.current) {
      setNotificationInstance(notificationApi);
      setMessageInstance(messageApi);
      initialized.current = true;
    }
  }, [notificationApi, messageApi]);

  useEffect(() => {
    dayjs.locale(locale === "zh" ? "zh-cn" : "en");
  }, [locale]);

  return (
    <ConfigProvider locale={locale === "zh" ? zhCN : enUS}>
      {notificationContextHolder}
      {messageContextHolder}
      {children}
    </ConfigProvider>
  );
}
