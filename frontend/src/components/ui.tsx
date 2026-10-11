import React, { useEffect, useRef } from "react";
import { X, ArrowLeft, ArrowRight, LoaderCircle } from "lucide-react";
import { Row } from "../services/api";
export const Badge = ({ children }: { children: React.ReactNode }) => (
  <span
    className={"badge " + String(children).toLowerCase().replaceAll(" ", "_")}
  >
    {String(children ?? "—").replaceAll("_", " ")}
  </span>
);
export const ErrorBox = ({ error }: { error: unknown }) =>
  error ? (
    <div className="error" role="alert">
      {error instanceof Error ? error.message : String(error)}
    </div>
  ) : null;
export const Loading = () => (
  <div className="empty">
    <LoaderCircle className="spin" /> Loading campus data…
  </div>
);
export function Title({
  title,
  sub,
  actions,
}: {
  title: string;
  sub: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="page-title">
      <div>
        <p className="eyebrow">FACEIQ / CAMPUS OPERATIONS</p>
        <h1>{title}</h1>
        <p>{sub}</p>
      </div>
      <div className="actions">{actions}</div>
    </div>
  );
}
export function Card({
  title,
  children,
  extra,
}: {
  title?: string;
  children: React.ReactNode;
  extra?: React.ReactNode;
}) {
  return (
    <section className="card">
      {title && (
        <div className="card-head">
          <h2>{title}</h2>
          {extra}
        </div>
      )}
      {children}
    </section>
  );
}
export function Stat({
  label,
  value,
  note,
}: {
  label: string;
  value: React.ReactNode;
  note?: string;
}) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong>{value ?? "—"}</strong>
      {note && <small>{note}</small>}
    </div>
  );
}
export function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}
export function Input({
  label,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <Field label={label}>
      <input aria-label={label} {...props} />
    </Field>
  );
}
export function Select({
  label,
  children,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement> & { label: string }) {
  return (
    <Field label={label}>
      <select aria-label={label} {...props}>
        {children}
      </select>
    </Field>
  );
}
export function Table({
  rows,
  columns,
  empty = "No records yet.",
}: {
  rows: Row[];
  columns: { label: string; render: (r: Row) => React.ReactNode }[];
  empty?: string;
}) {
  return rows.length ? (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.label}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.id ?? r.student_id ?? i}>
              {columns.map((c) => (
                <td key={c.label}>{c.render(r)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <div className="empty">{empty}</div>
  );
}
export function Pager({
  offset,
  total,
  limit = 25,
  onChange,
}: {
  offset: number;
  total: number;
  limit?: number;
  onChange: (n: number) => void;
}) {
  return (
    <div className="pager">
      <span>
        {total ? offset + 1 : 0}–{Math.min(offset + limit, total)} of {total}
      </span>
      <button
        className="ghost"
        disabled={!offset}
        onClick={() => onChange(Math.max(0, offset - limit))}
      >
        <ArrowLeft size={15} />
        Previous
      </button>
      <button
        className="ghost"
        disabled={offset + limit >= total}
        onClick={() => onChange(offset + limit)}
      >
        Next
        <ArrowRight size={15} />
      </button>
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    dialog.current?.showModal();
    return () => dialog.current?.close();
  }, []);
  return (
    <dialog
      ref={dialog}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <div className="modal-head">
        <h2>{title}</h2>
        <button className="ghost" aria-label="Close dialog" onClick={onClose}>
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function Confirm({
  title,
  text,
  onConfirm,
  onClose,
  busy = false,
}: {
  title: string;
  text: string;
  onConfirm: () => void;
  onClose: () => void;
  busy?: boolean;
}) {
  return (
    <Modal title={title} onClose={onClose}>
      <p>{text}</p>
      <div className="form-actions">
        <button className="ghost" onClick={onClose}>
          Cancel
        </button>
        <button disabled={busy} onClick={onConfirm}>
          Confirm
        </button>
      </div>
    </Modal>
  );
}
