import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

import AntdGlobalProvider from "@/contexts/AntdGlobalProvider";
import { AuthProvider } from "@/contexts/AuthContext";
import ReactQueryProvider from "@/contexts/ReactQueryProvider";
import { I18nProvider } from "@/i18n";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "LiteLLM Dashboard",
  description: "LiteLLM Proxy Admin UI",
  icons: { icon: "./favicon.ico" },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className={inter.className}>
        <ReactQueryProvider>
          <I18nProvider>
            <AntdGlobalProvider>
              <AuthProvider>{children}</AuthProvider>
            </AntdGlobalProvider>
          </I18nProvider>
        </ReactQueryProvider>
      </body>
    </html>
  );
}
