import type { Metadata } from "next";

import { CopilotKit } from "@copilotkit/react-core";

import "./globals.css";

export const metadata: Metadata = {
  title: "Segmentation Explorer",
  description: "Conversational Zoho CRM segmentation",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <CopilotKit runtimeUrl="/api/copilotkit">{children}</CopilotKit>
      </body>
    </html>
  );
}
