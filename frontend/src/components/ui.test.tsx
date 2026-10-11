import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Badge, Pager, ErrorBox } from "./ui";
import { dateTime } from "../services/api";
describe("operational UI", () => {
  it("clearly labels duplicate events", () => {
    render(<Badge>ALREADY_PRESENT</Badge>);
    expect(screen.getByText("ALREADY PRESENT")).toBeInTheDocument();
  });
  it("bounds pagination", () => {
    const change = vi.fn();
    render(<Pager offset={0} total={40} onChange={change} />);
    expect(screen.getByRole("button", { name: /Previous/ })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: /Next/ }));
    expect(change).toHaveBeenCalledWith(25);
  });
  it("renders backend validation errors accessibly", () => {
    render(<ErrorBox error={new Error("Session is closed")} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Session is closed");
  });
  it("treats server naive timestamps as UTC", () =>
    expect(dateTime("2026-01-01T12:00:00")).toBe(
      new Date("2026-01-01T12:00:00Z").toLocaleString(),
    ));
});
