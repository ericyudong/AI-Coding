"use client";

import { GlobalOutlined } from "@ant-design/icons";
import { Select } from "antd";
import { useI18n } from "./I18nProvider";
import type { Locale } from "./types";

export default function LanguageSwitcher({ className }: { className?: string }) {
  const { locale, setLocale, t } = useI18n();

  return (
    <Select
      size="small"
      className={className}
      value={locale}
      style={{ minWidth: 108 }}
      suffixIcon={<GlobalOutlined />}
      aria-label={t("common.language")}
      options={[
        { value: "zh", label: t("common.chinese") },
        { value: "en", label: t("common.english") },
      ]}
      onChange={(value: Locale) => setLocale(value)}
    />
  );
}
