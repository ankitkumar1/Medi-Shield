"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, getJSON } from "../../lib";
import { Badge, Shell } from "../../ui";

const AGENTS = ["classifier", "kyc", "claims", "policy", "fraud", "orchestrator"];

export default function CaseDetail() {
  const params = useParams();
  const caseId = params.id;
  const [item, setItem] = useState(null);
  const [error, setError] = useState("");
  const [decision, setDecision] = useState("APPROVE");
  const [note, setNote] = useState("");
  const [actor, setActor] = useState("ops");

  function load() {
    getJSON(`/cases/${caseId}`).then(setItem).catch((err) => setError(err.message));
  }

  useEffect(() => { load(); }, [caseId]);

  async function override(event) {
    event.preventDefault();
    const response = await fetch(api(`/cases/${caseId}/override`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, note, actor }),
    });
    if (!response.ok) {
      setError("Override failed");
      return;
    }
    setItem(await response.json());
    setNote("");
  }

  if (error) {
    return <Shell><p>{error}</p></Shell>;
  }
  if (!item) {
    return <Shell><p>Loading case…</p></Shell>;
  }

  return (
    <Shell>
      <h2>{item.case_id}</h2>
      <p className="muted">{item.original_filename} · {item.doc_type || "unclassified"}</p>
      <div className="detail">
        <img className="doc" alt="Uploaded document" src={api(item.file_url)} />
        <div>
          <section className="card panel">
            <h2>Decision</h2>
            <p><Badge value={item.decision} /> <Badge value={item.status} /></p>
            <p>Confidence {item.confidence ?? "—"}</p>
            <p>{item.justification}</p>
          </section>
          <section className="card panel" style={{ marginTop: 12 }}>
            <h2>Agent outputs</h2>
            {AGENTS.map((name) => (
              <details key={name}>
                <summary>{name}</summary>
                <pre>{JSON.stringify(item.agents?.[name] ?? "Not run", null, 2)}</pre>
              </details>
            ))}
          </section>
          <section className="card panel" style={{ marginTop: 12 }}>
            <h2>Override</h2>
            <form onSubmit={override}>
              <label>Reviewer</label>
              <input value={actor} onChange={(event) => setActor(event.target.value)} style={{ width: "100%", padding: 8 }} />
              <label>New decision</label>
              <select value={decision} onChange={(event) => setDecision(event.target.value)}>
                <option>APPROVE</option>
                <option>REJECT</option>
                <option>ESCALATE</option>
              </select>
              <label>Note</label>
              <textarea rows={3} value={note} onChange={(event) => setNote(event.target.value)} />
              <button type="submit">Save override</button>
            </form>
          </section>
          <section className="card panel" style={{ marginTop: 12 }}>
            <h2>Audit log</h2>
            <ul className="audit">
              {(item.audit || []).map((entry, index) => (
                <li key={index}>
                  <strong>{entry.action}</strong> · {entry.actor} · {entry.created_at}
                  <div>{entry.detail}</div>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </Shell>
  );
}
