import { Button } from "@tremor/react";
import type { TableProps } from "antd";
import { Table } from "antd";
import Title from "antd/es/typography/Title";
import React from "react";
import TableIconActionButton from "../../../common_components/IconActionButton/TableIconActionButtons/TableIconActionButton";
import { AlertingObject } from "./types";
import { useI18n } from "@/i18n";

type LoggingCallbacksProps = {
  callbacks: AlertingObject[];
  availableCallbacks?: Record<
    string,
    {
      litellm_callback_name: string;
      litellm_callback_params: string[];
      ui_callback_name: string;
    }
  >;
  onTest?: (callback: AlertingObject) => void | Promise<void>;
  onEdit?: (callback: AlertingObject) => void;
  onDelete?: (callback: AlertingObject) => void;
  onAdd?: () => void;
};

type CallbackRow = AlertingObject & {
  id?: string;
  mode?: "success" | "failure" | "info" | string;
};



export const LoggingCallbacksTable: React.FC<LoggingCallbacksProps> = ({
  callbacks,
  availableCallbacks = {},
  onTest = () => {},
  onEdit = () => {},
  onDelete = () => {},
  onAdd = () => {},
}) => {
  const { t } = useI18n();
  const columns: TableProps<CallbackRow>["columns"] = [
    {
      title: <span className="font-medium text-gray-700">{t("settings.logging.callbackName")}</span>,
      dataIndex: "name",
      key: "name",
      render: (_: string, record: CallbackRow) => {
        const id = record.name;
        console.log("availableCallbacks", availableCallbacks);
        const displayName = availableCallbacks[id]?.ui_callback_name || id;
        return <div className="font-medium text-gray-800">{displayName}</div>;
      },
    },
    {
      title: <span className="font-medium text-gray-700">{t("settings.logging.mode")}</span>,
      key: "mode",
      render: (_: unknown, record: CallbackRow) => {
        const mode = record.mode || "success";
        const modeLabelMap: Record<string, string> = {
          success: t("settings.logging.modeSuccess"),
          failure: t("settings.logging.modeFailure"),
          success_and_failure: t("settings.logging.modeBoth"),
        };
        const label = modeLabelMap[mode] || mode;
        const badgeClass =
          mode === "success"
            ? "bg-green-100 text-green-800"
            : mode === "failure"
              ? "bg-red-100 text-red-800"
              : "bg-blue-100 text-blue-800";
        return (
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${badgeClass}`}>
            {label}
          </span>
        );
      },
      width: 240,
    },
    {
      title: <span className="font-medium text-gray-700 text-right w-full block">{t("common.actions")}</span>,
      key: "actions",
      align: "right",
      render: (_: unknown, record: CallbackRow) => (
        <div className="flex justify-end gap-2">
          <TableIconActionButton variant="Test" tooltipText={t("settings.logging.testCallback")} onClick={() => onTest(record)} />
          <TableIconActionButton variant="Edit" tooltipText={t("settings.logging.editCallback")} onClick={() => onEdit(record)} />
          <TableIconActionButton variant="Delete" tooltipText={t("settings.logging.deleteCallback")} onClick={() => onDelete(record)} />
        </div>
      ),
      width: 240,
    },
  ];
  return (
    <>
      <div className="w-full mt-4">
        <Button onClick={onAdd} className="mx-auto">
          {t("settings.logging.addCallback")}
        </Button>
        <div className="flex justify-between items-center my-2">
          <Title level={4}>{t("settings.logging.activeCallbacks")}</Title>
        </div>
        {/* Empty state */}
        {callbacks.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-8 bg-gray-50 border border-gray-200 rounded-lg">
            <div className="text-center">
              <h3 className="text-lg font-medium text-gray-700 mb-2">{t("settings.logging.noCallbacks")}</h3>
              <p className="text-gray-500">{t("settings.logging.noCallbacksHint")}</p>
            </div>
          </div>
        ) : (
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <Table
              columns={columns}
              dataSource={callbacks as CallbackRow[]}
              rowKey={(record) => record.name}
              pagination={false}
              rowClassName={() => "hover:bg-gray-50"}
            />
          </div>
        )}
      </div>
    </>
  );
};
