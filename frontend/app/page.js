"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getJSON } from "./lib";
import { Badge, Shell } from "./ui";

export default function Dashboard() {
  const [cases, setCases] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    getJSON("/cases").then((data) => setCases(data.cases)).catch((err) => setError(err.message));
  }, []);

  return (
    <Shell>
      <h2>Incoming cases</h2>
      <p className="muted">Each upload is classified, checked, and given a decision.</p>
      {error && <p>{error}</p>}
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Case</th>
              <th>File</th>
              <th>Type</th>
              <th>Status</th>
              <th>Decision</th>
            </tr>
          </thead>
          <tbody>
            {cases.map((item) => (
              <tr key={item.case_id}>
                <td><Link href={`/cases/${item.case_id}`}>{item.case_id}</Link></td>
                <td>{item.original_filename}</td>
                <td>{item.doc_type || "—"}</td>
                <td><Badge value={item.status} /></td>
                <td><Badge value={item.decision} /></td>
              </tr>
            ))}
            {cases.length === 0 && (
              <tr><td colSpan={5}>No cases yet. Upload one from the API docs, then refresh.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Shell>
  );
}
