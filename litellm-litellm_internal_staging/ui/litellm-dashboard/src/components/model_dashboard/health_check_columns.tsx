import { ColumnDef } from "@tanstack/react-table";
import { Tooltip, Checkbox } from "antd";
import { Text } from "@tremor/react";
import { InformationCircleIcon, PlayIcon, RefreshIcon } from "@heroicons/react/outline";
import { Team } from "@/components/key_team_helpers/key_list";
import en from "@/i18n/locales/en";
import type { MessageKey, TranslateParams } from "@/i18n";

interface HealthCheckData {
  model_name: string;
  model_info: {
    id: string;
    created_at?: string;
    team_id?: string;
  };
  provider?: string;
  litellm_model_name?: string;
  health_status: string;
  last_check: string;
  last_success: string;
  health_loading: boolean;
  health_error?: string;
  health_full_error?: string;
}

interface HealthStatus {
  status: string;
  lastCheck: string;
  lastSuccess?: string;
  loading: boolean;
  error?: string;
  fullError?: string;
  successResponse?: any;
}

type TranslateFn = (key: MessageKey, params?: TranslateParams) => string;

export const healthCheckColumns = (
  modelHealthStatuses: { [key: string]: HealthStatus },
  selectedModelsForHealth: string[],
  allModelsSelected: boolean,
  handleModelSelection: (modelId: string, checked: boolean) => void,
  handleSelectAll: (checked: boolean) => void,
  runIndividualHealthCheck: (modelId: string) => void,
  getStatusBadge: (status: string) => JSX.Element,
  getDisplayModelName: (model: any) => string,
  showErrorModal?: (modelName: string, cleanedError: string, fullError: string) => void,
  showSuccessModal?: (modelName: string, response: any) => void,
  setSelectedModelId?: (modelId: string) => void,
  teams?: Team[] | null,
  t?: TranslateFn,
): ColumnDef<HealthCheckData>[] => {
  const tr: TranslateFn = t ?? ((key) => (en as Record<string, string>)[key] ?? key);
  return [
  {
    header: () => (
      <div className="flex items-center gap-2">
        <Checkbox
          checked={allModelsSelected}
          indeterminate={selectedModelsForHealth.length > 0 && !allModelsSelected}
          onChange={(e) => handleSelectAll(e.target.checked)}
          onClick={(e) => e.stopPropagation()}
        />
        <span>{tr("models.colModelId")}</span>
      </div>
    ),
    accessorKey: "model_info.id",
    enableSorting: true,
    sortingFn: "alphanumeric",
    cell: ({ row }) => {
      const model = row.original;
      const modelId = model.model_info?.id ?? "";
      const isSelected = selectedModelsForHealth.includes(modelId);

      return (
        <div className="flex items-center gap-2">
          <Checkbox
            checked={isSelected}
            onChange={(e) => handleModelSelection(modelId, e.target.checked)}
            onClick={(e) => e.stopPropagation()}
          />
          <Tooltip title={model.model_info.id}>
            <div
              className="font-mono text-blue-500 bg-blue-50 hover:bg-blue-100 text-xs font-normal px-2 py-0.5 text-left w-full truncate whitespace-nowrap cursor-pointer max-w-[15ch]"
              onClick={() => setSelectedModelId && setSelectedModelId(model.model_info.id)}
            >
              {model.model_info.id}
            </div>
          </Tooltip>
        </div>
      );
    },
  },
  {
    header: tr("models.modelName"),
    accessorKey: "model_name",
    enableSorting: true,
    sortingFn: "alphanumeric",
    cell: ({ row }) => {
      const model = row.original;
      const displayName = getDisplayModelName(model) || model.model_name;

      return (
        <div className="font-medium text-sm">
          <Tooltip title={displayName}>
            <div className="truncate max-w-[200px]">{displayName}</div>
          </Tooltip>
        </div>
      );
    },
  },
  {
    header: tr("models.teamAlias"),
    accessorKey: "model_info.team_id",
    enableSorting: true,
    sortingFn: "alphanumeric",
    cell: ({ row }) => {
      const model = row.original;
      const teamId = model.model_info?.team_id;

      if (!teamId) {
        return <span className="text-gray-400 text-sm">-</span>;
      }

      const team = teams?.find((t) => t.team_id === teamId);
      const teamAlias = team?.team_alias || teamId;

      return (
        <div className="text-sm">
          <Tooltip title={teamAlias}>
            <div className="truncate max-w-[150px]">{teamAlias}</div>
          </Tooltip>
        </div>
      );
    },
  },
  {
    header: tr("models.healthStatus"),
    accessorKey: "health_status",
    enableSorting: true,
    sortingFn: (rowA, rowB, columnId) => {
      const statusA = (rowA.getValue("health_status") as string) || "unknown";
      const statusB = (rowB.getValue("health_status") as string) || "unknown";

      // Define sorting order: healthy > checking > unknown > unhealthy
      const statusOrder = { healthy: 0, checking: 1, unknown: 2, unhealthy: 3 };
      const orderA = statusOrder[statusA as keyof typeof statusOrder] ?? 4;
      const orderB = statusOrder[statusB as keyof typeof statusOrder] ?? 4;

      return orderA - orderB;
    },
    cell: ({ row }) => {
      const model = row.original;
      const healthStatus = {
        status: model.health_status,
        loading: model.health_loading,
        error: model.health_error,
      };

      if (healthStatus.loading) {
        return (
          <div className="flex items-center space-x-2">
            <div className="flex space-x-1">
              <div className="w-2 h-2 bg-indigo-500 rounded-full animate-pulse"></div>
              <div
                className="w-2 h-2 bg-indigo-500 rounded-full animate-pulse"
                style={{ animationDelay: "0.2s" }}
              ></div>
              <div
                className="w-2 h-2 bg-indigo-500 rounded-full animate-pulse"
                style={{ animationDelay: "0.4s" }}
              ></div>
            </div>
            <Text className="text-gray-600 text-sm">{tr("models.checking")}</Text>
          </div>
        );
      }

      const modelId = model.model_info?.id ?? "";
      const displayName = getDisplayModelName(model) || model.model_name;
      const hasSuccessResponse = healthStatus.status === "healthy" && modelHealthStatuses[modelId]?.successResponse;

      return (
        <div className="flex items-center space-x-2">
          {getStatusBadge(healthStatus.status)}
          {hasSuccessResponse && showSuccessModal && (
            <Tooltip title={tr("health.viewResponse")} placement="top">
              <button
                onClick={() => showSuccessModal(displayName, modelHealthStatuses[modelId]?.successResponse)}
                className="p-1 text-green-600 hover:text-green-800 hover:bg-green-50 rounded cursor-pointer transition-colors"
              >
                <InformationCircleIcon className="h-4 w-4" />
              </button>
            </Tooltip>
          )}
        </div>
      );
    },
  },
  {
    header: tr("models.errorDetails"),
    accessorKey: "health_error",
    enableSorting: false,
    cell: ({ row }) => {
      const model = row.original;
      const modelId = model.model_info?.id ?? "";
      const displayName = getDisplayModelName(model) || model.model_name;
      const healthStatus = modelHealthStatuses[modelId];

      if (!healthStatus?.error) {
        return <Text className="text-gray-400 text-sm">{tr("models.noErrors")}</Text>;
      }

      const cleanedError = healthStatus.error;
      const fullError = healthStatus.fullError || healthStatus.error;

      return (
        <div className="flex items-center space-x-2">
          <div className="max-w-[200px]">
            <Tooltip title={cleanedError} placement="top">
              <Text className="text-red-600 text-sm truncate">{cleanedError}</Text>
            </Tooltip>
          </div>
          {showErrorModal && fullError !== cleanedError && (
            <Tooltip title={tr("health.viewFullError")} placement="top">
              <button
                onClick={() => showErrorModal(displayName, cleanedError, fullError)}
                className="p-1 text-red-600 hover:text-red-800 hover:bg-red-50 rounded cursor-pointer transition-colors"
              >
                <InformationCircleIcon className="h-4 w-4" />
              </button>
            </Tooltip>
          )}
        </div>
      );
    },
  },
  {
    header: tr("models.lastCheck"),
    accessorKey: "last_check",
    enableSorting: true,
    sortingFn: (rowA, rowB, columnId) => {
      const lastCheckA = (rowA.getValue("last_check") as string) || tr("models.neverChecked");
      const lastCheckB = (rowB.getValue("last_check") as string) || tr("models.neverChecked");

      // Handle special cases
      if (lastCheckA === tr("models.neverChecked") && lastCheckB === tr("models.neverChecked")) return 0;
      if (lastCheckA === tr("models.neverChecked")) return 1; // Never checked goes to bottom
      if (lastCheckB === tr("models.neverChecked")) return -1;
      if (lastCheckA === tr("health.checkInProgress") && lastCheckB === tr("health.checkInProgress")) return 0;
      if (lastCheckA === tr("health.checkInProgress")) return -1; // In progress goes to top
      if (lastCheckB === tr("health.checkInProgress")) return 1;

      // Parse dates for comparison
      const dateA = new Date(lastCheckA);
      const dateB = new Date(lastCheckB);

      // If dates are invalid, treat as never checked
      if (isNaN(dateA.getTime()) && isNaN(dateB.getTime())) return 0;
      if (isNaN(dateA.getTime())) return 1;
      if (isNaN(dateB.getTime())) return -1;

      // Sort by date (most recent first)
      return dateB.getTime() - dateA.getTime();
    },
    cell: ({ row }) => {
      const model = row.original;

      return (
        <Text className="text-gray-600 text-sm">
      return (
        <Text className="text-gray-600 text-sm">
          {model.health_loading
            ? tr("health.checkInProgress")
            : model.last_check === "None"
              ? tr("health.none")
              : model.last_check}
        </Text>
      );
        </Text>
      );
    },
  },
  {
    header: tr("models.lastSuccess"),
    accessorKey: "last_success",
    enableSorting: true,
    sortingFn: (rowA, rowB, columnId) => {
      const lastSuccessA = (rowA.getValue("last_success") as string) || tr("models.neverSucceeded");
      const lastSuccessB = (rowB.getValue("last_success") as string) || tr("models.neverSucceeded");

      // Handle special cases
      if (lastSuccessA === tr("models.neverSucceeded") && lastSuccessB === tr("models.neverSucceeded")) return 0;
      if (lastSuccessA === tr("models.neverSucceeded")) return 1; // Never succeeded goes to bottom
      if (lastSuccessB === tr("models.neverSucceeded")) return -1;
      if (lastSuccessA === "None" && lastSuccessB === "None") return 0;
      if (lastSuccessA === "None") return 1; // None goes to bottom
      if (lastSuccessB === "None") return -1;

      // Parse dates for comparison
      const dateA = new Date(lastSuccessA);
      const dateB = new Date(lastSuccessB);

      // If dates are invalid, treat as never succeeded
      if (isNaN(dateA.getTime()) && isNaN(dateB.getTime())) return 0;
      if (isNaN(dateA.getTime())) return 1;
      if (isNaN(dateB.getTime())) return -1;

      // Sort by date (most recent first)
      return dateB.getTime() - dateA.getTime();
    },
    cell: ({ row }) => {
      const model = row.original;
      const modelId = model.model_info?.id ?? "";
      const healthStatus = modelHealthStatuses[modelId];
      const lastSuccess = healthStatus?.lastSuccess || "None";

      return (
        <Text className="text-gray-600 text-sm">
          {lastSuccess === "None" ? tr("health.none") : lastSuccess}
        </Text>
      );
    },
  },
  {
    header: tr("models.colActions"),
    id: "actions",
    cell: ({ row }) => {
      const model = row.original;
      const modelId = model.model_info?.id ?? "";

      const hasExistingStatus = model.health_status && model.health_status !== "none";
      const tooltipText = model.health_loading
        ? tr("models.checking")
        : hasExistingStatus
          ? tr("models.rerunHealthCheck")
          : tr("models.runHealthCheck");

      return (
        <Tooltip title={tooltipText} placement="top">
          <button
            data-testid="run-health-check-btn"
            className={`p-2 rounded-md transition-colors ${
              model.health_loading
                ? "text-gray-400 cursor-not-allowed bg-gray-100"
                : "text-indigo-600 hover:text-indigo-700 hover:bg-indigo-50"
            }`}
            onClick={() => {
              if (!model.health_loading) {
                runIndividualHealthCheck(modelId);
              }
            }}
            disabled={model.health_loading}
          >
            {model.health_loading ? (
              <div className="flex space-x-1">
                <div className="w-1 h-1 bg-gray-400 rounded-full animate-pulse"></div>
                <div
                  className="w-1 h-1 bg-gray-400 rounded-full animate-pulse"
                  style={{ animationDelay: "0.2s" }}
                ></div>
                <div
                  className="w-1 h-1 bg-gray-400 rounded-full animate-pulse"
                  style={{ animationDelay: "0.4s" }}
                ></div>
              </div>
            ) : hasExistingStatus ? (
              <RefreshIcon className="h-4 w-4" />
            ) : (
              <PlayIcon className="h-4 w-4" />
            )}
          </button>
        </Tooltip>
      );
    },
    enableSorting: false,
  },
];
};
