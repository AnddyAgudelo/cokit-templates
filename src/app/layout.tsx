"use client";

import "./globals.css";
import "@copilotkit/react-core/v2/styles.css";

import { CopilotKit } from "@copilotkit/react-core/v2";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <title>Segmentation Explorer</title>
      </head>
      <body>
        <CopilotKit
          runtimeUrl="/api/copilotkit"
          openGenerativeUI={{}}
          useSingleEndpoint={false}
        >
          {children}
        </CopilotKit>
      </body>
    </html>
  );
}
