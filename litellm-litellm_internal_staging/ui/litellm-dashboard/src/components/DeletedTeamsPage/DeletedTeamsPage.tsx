"use client";
import { useI18n } from "@/i18n";
import { Alert } from "antd";
import { useDeletedTeams } from "@/app/(dashboard)/hooks/teams/useTeams";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";
import { DeletedTeamsTable } from "./DeletedTeamsTable/DeletedTeamsTable";

export default function DeletedTeamsPage() {
  const { t } = useI18n();
  const { premiumUser } = useAuthorized();
  const {
    data: teamsData,
    isPending: isLoading,
    isFetching,
  } = useDeletedTeams(1, 100);

  return (
    <div className="flex flex-col gap-4">
      {!premiumUser && (
        <Alert
          type="info"
          banner
          showIcon
          message={t("deletedTeams.enterpriseTitle")}
          description={t("deletedTeams.enterpriseDesc")}
        />
      )}
      <DeletedTeamsTable
        teams={teamsData || []}
        isLoading={isLoading}
        isFetching={isFetching}
      />
    </div>
  );
}
