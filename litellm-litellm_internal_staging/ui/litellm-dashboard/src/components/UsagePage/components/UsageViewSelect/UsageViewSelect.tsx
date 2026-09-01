import {
  BankOutlined,
  BarChartOutlined,
  GlobalOutlined,
  LineChartOutlined,
  RobotOutlined,
  ShoppingCartOutlined,
  TagsOutlined,
  TeamOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { Badge, Select } from "antd";
import React, { useMemo } from "react";
import { useI18n, type MessageKey } from "@/i18n";

export type UsageOption =
  | "global"
  | "my-usage"
  | "organization"
  | "team"
  | "customer"
  | "tag"
  | "agent"
  | "user"
  | "user-agent-activity";

export interface UsageViewSelectProps {
  value: UsageOption;
  onChange: (value: UsageOption) => void;
  isAdmin: boolean;
  canViewTagUsage?: boolean;
  title?: string;
  description?: string;
  "data-id"?: string;
}

interface OptionConfig {
  value: UsageOption;
  labelKey: MessageKey;
  descriptionKey: MessageKey;
  icon: React.ReactNode;
  adminOnly?: boolean;
  showForAdminKey?: MessageKey;
  showForNonAdminKey?: MessageKey;
  descriptionForAdminKey?: MessageKey;
  descriptionForNonAdminKey?: MessageKey;
  badgeText?: string;
}

const OPTIONS: OptionConfig[] = [
  {
    value: "global",
    labelKey: "usage.global",
    showForAdminKey: "usage.global",
    showForNonAdminKey: "usage.yourUsage",
    descriptionKey: "usage.globalDesc",
    descriptionForAdminKey: "usage.globalDesc",
    descriptionForNonAdminKey: "usage.yourUsageDesc",
    icon: <GlobalOutlined style={{ fontSize: "16px" }} />,
  },
  {
    value: "my-usage",
    labelKey: "usage.myUsage",
    descriptionKey: "usage.myUsageDesc",
    icon: <UserOutlined style={{ fontSize: "16px" }} />,
    adminOnly: true,
  },
  {
    value: "organization",
    labelKey: "usage.organization",
    showForAdminKey: "usage.organization",
    showForNonAdminKey: "usage.yourOrganization",
    descriptionKey: "usage.organizationDesc",
    descriptionForAdminKey: "usage.organizationDescAdmin",
    descriptionForNonAdminKey: "usage.organizationDescUser",
    icon: <BankOutlined style={{ fontSize: "16px" }} />,
  },
  {
    value: "team",
    labelKey: "usage.team",
    descriptionKey: "usage.teamDesc",
    icon: <TeamOutlined style={{ fontSize: "16px" }} />,
  },
  {
    value: "customer",
    labelKey: "usage.customer",
    descriptionKey: "usage.customerDesc",
    icon: <ShoppingCartOutlined style={{ fontSize: "16px" }} />,
    adminOnly: true,
  },
  {
    value: "tag",
    labelKey: "usage.tag",
    descriptionKey: "usage.tagDesc",
    icon: <TagsOutlined style={{ fontSize: "16px" }} />,
    adminOnly: true,
  },
  {
    value: "agent",
    labelKey: "usage.agent",
    descriptionKey: "usage.agentDesc",
    icon: <RobotOutlined style={{ fontSize: "16px" }} />,
    adminOnly: true,
  },
  {
    value: "user",
    labelKey: "usage.user",
    descriptionKey: "usage.userDesc",
    icon: <UserOutlined style={{ fontSize: "16px" }} />,
    adminOnly: true,
  },
  {
    value: "user-agent-activity",
    labelKey: "usage.userAgentActivity",
    descriptionKey: "usage.userAgentActivityDesc",
    icon: <LineChartOutlined style={{ fontSize: "16px" }} />,
    adminOnly: true,
  },
];

export const UsageViewSelect: React.FC<UsageViewSelectProps> = ({
  value,
  onChange,
  isAdmin,
  canViewTagUsage = false,
  title,
  description,
  "data-id": dataId,
}) => {
  const { t } = useI18n();
  const resolvedTitle = title ?? t("usage.viewTitle");
  const resolvedDescription = description ?? t("usage.viewDescription");

  const filteredOptions = useMemo(() => {
    return OPTIONS.filter((option) => {
      if (option.value === "tag" && canViewTagUsage) {
        return true;
      }
      if (option.adminOnly && !isAdmin) {
        return false;
      }
      return true;
    }).map((option) => {
      let label = t(option.labelKey);
      let desc = t(option.descriptionKey);
      if (option.showForAdminKey && option.showForNonAdminKey) {
        label = isAdmin ? t(option.showForAdminKey) : t(option.showForNonAdminKey);
      }
      if (option.descriptionForAdminKey && option.descriptionForNonAdminKey) {
        desc = isAdmin ? t(option.descriptionForAdminKey) : t(option.descriptionForNonAdminKey);
      }
      return {
        value: option.value,
        label,
        description: desc,
        icon: option.icon,
        badgeText: option.badgeText,
      };
    });
  }, [canViewTagUsage, isAdmin, t]);

  return (
    <div className="w-full" data-id={dataId}>
      <div className="flex flex-wrap items-center justify-start gap-4">
        <div className="flex items-stretch gap-2 min-w-0">
          <div className="flex-shrink-0 flex items-center">
            <BarChartOutlined style={{ fontSize: "32px" }} />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-gray-900 mb-0.5 leading-tight">{resolvedTitle}</h3>
            <p className="text-xs text-gray-600 leading-tight">{resolvedDescription}</p>
          </div>
        </div>
        <div className="flex-shrink-0">
          <Select
            value={value}
            onChange={onChange}
            className="w-54 sm:w-64 md:w-72"
            size="large"
            options={filteredOptions.map((opt) => ({
              value: opt.value,
              label: opt.label,
            }))}
            optionRender={(option) => {
              const opt = filteredOptions.find((o) => o.value === option.value);
              if (!opt) return option.label;
              return (
                <div className="flex items-center gap-2 py-1">
                  <div className="flex-shrink-0 mt-0.5">{opt.icon}</div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-900">{opt.label}</div>
                    <div className="text-xs text-gray-600 mt-0.5">{opt.description}</div>
                  </div>
                  {opt.badgeText && (
                    <div className="items-center">
                      <Badge color="blue" count={opt.badgeText} />
                    </div>
                  )}
                </div>
              );
            }}
            labelRender={(props) => {
              const opt = filteredOptions.find((o) => o.value === props.value);
              if (!opt) return props.label;
              return (
                <div className="flex items-center gap-2">
                  <div>{opt.icon}</div>
                  <span className="text-sm">{opt.label}</span>
                </div>
              );
            }}
          />
        </div>
      </div>
    </div>
  );
};
