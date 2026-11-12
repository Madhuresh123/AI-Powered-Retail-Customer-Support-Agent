import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Data Insight",
  description: "Dataset management and data preview platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
