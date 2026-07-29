import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectCard } from "../components/ProjectCard";
import { PROJECT_ID, projectFixture } from "../test/paintProjectFixtures";

describe("ProjectCard", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the five-field contract and an explicit open action", () => {
    vi.spyOn(Date, "now").mockReturnValue(
      new Date("2026-07-27T08:10:00.000Z").getTime(),
    );
    render(
      <MemoryRouter>
        <ProjectCard
          project={projectFixture({
            description: "Card descriptions are detail-only.",
            title: "Courtyard figure repaint",
          })}
        />
      </MemoryRouter>,
    );

    const card = screen.getByRole("article");
    expect(
      within(card).getByRole("heading", { name: "Courtyard figure repaint" }),
    ).toBeInTheDocument();
    expect(within(card).getByText("Primary image not added")).toBeInTheDocument();
    expect(within(card).getByLabelText("Workflow status: Draft")).toBeInTheDocument();
    expect(within(card).getByText("No active review gate")).toBeInTheDocument();
    expect(within(card).getByText("just now")).toBeInTheDocument();
    expect(
      within(card).getByLabelText(
        "Updated July 27, 2026 at 8:10:00 AM UTC",
      ),
    ).toHaveAttribute("datetime", "2026-07-27T08:10:00.000Z");
    expect(
      within(card).getByRole("link", {
        name: "Open project Courtyard figure repaint",
      }),
    ).toHaveAttribute("href", `/paintpilot/projects/${PROJECT_ID}`);

    expect(within(card).queryByText("Card descriptions are detail-only."))
      .not.toBeInTheDocument();
    expect(within(card).queryByText("Cel Shading")).not.toBeInTheDocument();
    expect(within(card).queryByText("Planning only")).not.toBeInTheDocument();
    expect(within(card).queryByText("Created")).not.toBeInTheDocument();
  });

  it("reflects persisted primary-image and formal review-gate facts", () => {
    render(
      <MemoryRouter>
        <ProjectCard
          project={projectFixture({
            current_image_asset_id: "33333333-3333-4333-8333-333333333333",
            status: "IMAGE_REVIEW_REQUIRED",
          })}
        />
      </MemoryRouter>,
    );

    const card = screen.getByRole("article");
    expect(within(card).getByText("Primary image stored")).toBeInTheDocument();
    expect(card.querySelector(".review-gate")).toHaveTextContent(
      "Image review required",
    );
  });
});
