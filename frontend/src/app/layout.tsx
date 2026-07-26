import type { Metadata } from "next";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "AiSummryIO — סיכום חכם לפי מזהה",
  description: "סיכומים מלאים, תהליכי עבודה וראיות ממקורות ארגוניים",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="he" dir="rtl">
      <body>{children}</body>
    </html>
  );
}

