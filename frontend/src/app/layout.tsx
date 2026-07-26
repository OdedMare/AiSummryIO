import type { Metadata } from "next";
// Leaflet ships its own z-index scale (panes 200–700, controls up to 1000).
// `MapWorkspace` loads it via `next/dynamic`, so its stylesheet would be
// injected *after* `globals.css` and win every equal-specificity conflict —
// letting the map paint over modals. Importing it here pins it ahead of the
// app's styles, which then override it as intended.
import "leaflet/dist/leaflet.css";
import "leaflet-draw/dist/leaflet.draw.css";
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
      <body>
        <a className="skip-link" href="#main-workspace">דלגו לתוכן הסיכום</a>
        {children}
      </body>
    </html>
  );
}
