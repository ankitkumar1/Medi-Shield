import "./globals.css";

export const metadata = {
  title: "Medi-Shield",
  description: "Case management for document intake",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
