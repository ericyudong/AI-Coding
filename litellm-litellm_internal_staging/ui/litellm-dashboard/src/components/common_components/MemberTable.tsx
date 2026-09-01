import { Member } from "@/components/networking";
import { CrownOutlined, InfoCircleOutlined, UserAddOutlined, UserOutlined } from "@ant-design/icons";
import { Button, Space, Table, Tag, Tooltip, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import React from "react";
import TableIconActionButton from "./IconActionButton/TableIconActionButtons/TableIconActionButton";
import { useI18n } from "@/i18n";

const { Text } = Typography;

export interface MemberTableProps {
  members: Member[];
  canEdit: boolean;
  onEdit: (member: Member) => void;
  onDelete: (member: Member) => void;
  onAddMember?: () => void;
  roleColumnTitle?: string;
  roleTooltip?: string;
  extraColumns?: ColumnsType<Member>;
  showDeleteForMember?: (member: Member) => boolean;
  emptyText?: string;
}

export default function MemberTable({
  members,
  canEdit,
  onEdit,
  onDelete,
  onAddMember,
  roleColumnTitle: roleColumnTitleProp,
  roleTooltip,
  extraColumns = [],
  showDeleteForMember,
  emptyText,
}: MemberTableProps) {
  const { t } = useI18n();
  const roleColumnTitle = roleColumnTitleProp ?? t("members.role");
  const baseColumns: ColumnsType<Member> = [
    {
      title: t("members.userEmail"),
      dataIndex: "user_email",
      key: "user_email",
      render: (email: string | null) => <Text>{email || "-"}</Text>,
    },
    {
      title: t("members.userId"),
      dataIndex: "user_id",
      key: "user_id",
      render: (userId: string | null) =>
        userId === "default_user_id" ? (
          <Tag color="blue">{t("members.defaultProxyAdmin")}</Tag>
        ) : (
          <Text>{userId || "-"}</Text>
        ),
    },
    {
      title: roleTooltip ? (
        <Space direction="horizontal">
          {roleColumnTitle}
          <Tooltip title={roleTooltip}>
            <InfoCircleOutlined />
          </Tooltip>
        </Space>
      ) : (
        roleColumnTitle
      ),
      dataIndex: "role",
      key: "role",
      render: (role: string) => (
        <Space>
          {role?.toLowerCase() === "admin" || role?.toLowerCase() === "org_admin" ? (
            <CrownOutlined />
          ) : (
            <UserOutlined />
          )}
          <Text style={{ textTransform: "capitalize" }}>{role || "-"}</Text>
        </Space>
      ),
    },
    ...extraColumns,
    {
      title: t("members.actions"),
      key: "actions",
      fixed: "right" as const,
      width: 120,
      render: (_: unknown, record: Member) =>
        canEdit ? (
          <Space>
            <TableIconActionButton
              variant="Edit"
              tooltipText={t("members.editMember")}
              dataTestId="edit-member"
              onClick={() => onEdit(record)}
            />
            {(!showDeleteForMember || showDeleteForMember(record)) && (
              <TableIconActionButton
                variant="Delete"
                tooltipText={t("members.deleteMember")}
                dataTestId="delete-member"
                onClick={() => onDelete(record)}
              />
            )}
          </Space>
        ) : null,
    },
  ];

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      <span className="inline-flex text-sm text-gray-700">
        {members.length !== 1 ? t("members.countPlural", { count: members.length }) : t("members.count", { count: members.length })}
      </span>
      <Table
        columns={baseColumns}
        dataSource={members}
        rowKey={(record) => record.user_id ?? record.user_email ?? JSON.stringify(record)}
        pagination={false}
        size="small"
        scroll={{ x: "max-content" }}
        locale={emptyText ? { emptyText } : undefined}
      />
      {onAddMember && canEdit && (
        <Button icon={<UserAddOutlined />} type="primary" onClick={onAddMember}>
          {t("members.addMember")}
        </Button>
      )}
    </Space>
  );
}
