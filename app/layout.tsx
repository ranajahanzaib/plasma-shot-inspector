import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title:
    "Plasma Shot Inspector — Experimental integrity. Equilibrium confidence.",
  description:
    "A transparent research workstation for FAIR-MAST shot inspection and quality auditing.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
