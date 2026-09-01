import React, { useState } from "react";
import { CopyToClipboard } from "react-copy-to-clipboard";
import { Button } from "antd";
import MessageManager from "@/components/molecules/message_manager";
import { useI18n } from "@/i18n";

interface CreatedKeyDisplayProps {
  apiKey: string;
}

/**
 * Shared component for displaying a newly-created virtual key.
 * Used on the Virtual Keys page and in the Add Agent wizard.
 */
const CreatedKeyDisplay: React.FC<CreatedKeyDisplayProps> = ({ apiKey }) => {
  const [copied, setCopied] = useState(false);
  const { t } = useI18n();

  const handleCopy = () => {
    setCopied(true);
    MessageManager.success(t("keys.copiedClipboard"));
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div>
      <p className="mb-2">
        {t("keys.createdDisplayWarningBefore")}
        <b>{t("keys.createdDisplayWarningBold")}</b>
        {t("keys.createdDisplayWarningAfter")}
      </p>

      <p className="text-sm text-gray-600 mt-3 mb-1">{t("keys.virtualKeyLabel")}</p>
      <div
        style={{
          background: "#f8f8f8",
          padding: "10px",
          borderRadius: "5px",
          marginBottom: "10px",
        }}
      >
        <pre style={{ wordWrap: "break-word", whiteSpace: "normal", margin: 0 }}>{apiKey}</pre>
      </div>

      <CopyToClipboard text={apiKey} onCopy={handleCopy}>
        <Button type="primary" style={{ marginTop: 12 }}>
          {copied ? t("common.copied") : t("keys.copyVirtualKey")}
        </Button>
      </CopyToClipboard>
    </div>
  );
};

export default CreatedKeyDisplay;
