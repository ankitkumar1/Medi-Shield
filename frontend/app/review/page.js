"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getJSON } from "../lib";
import { Badge, Shell } from "../ui";

export default function ReviewQueue() {
  const [cases, setCases] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    getJSON("/review").then((data) => setCases(data.cases)).catch((err) => setError(err.message));
  }, []);

  return (
    <Shell>
      <h2>Human review queue</h2>
      <p className="muted">Escalated cases waiting for an operations override.</p>
      {error && <p>{error}</p>}
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Case</th>
              <th>File</th>
              <th>Why it was escalated</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {cases.map((item) => (
              <tr key={item.case_id}>
                <td><Link href={`/cases/${item.case_id}`}>{item.case_id}</Link></td>
                <td>{item.original_filename}</td>
                <td>{item.justification}</td>
                <td><Badge value={item.status} /></td>
              </tr>
            ))}
            {cases.length === 0 && <tr><td colSpan={4}>The queue is empty.</td></tr>}
          </tbody>
        </table>
      </div>
    </Shell>
  );
}
