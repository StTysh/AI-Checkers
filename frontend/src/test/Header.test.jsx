import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Header from "../components/UI/Header";

describe("Header", () => {
  it("links backend docs through the relative docs path", () => {
    render(<Header />);

    const docsLink = screen.getByRole("link", { name: /backend docs/i });
    expect(docsLink).toHaveAttribute("href", "/docs");
    expect(docsLink).toHaveAttribute("target", "_blank");
  });
});
