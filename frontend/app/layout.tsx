import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ECDAT",
  description: "Explainable Cryptographic Discovery and Migration Planning"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
