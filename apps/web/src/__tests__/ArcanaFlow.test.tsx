import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { TarotReading } from "../api/arcana";
import { AppRoutes } from "../router/AppRoutes";

const READING_ID = "41414141-4141-4141-8141-414141414141";
const now = "2026-08-11T08:00:00Z";

function response(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function reading(status: TarotReading["status"]): TarotReading {
  const cards = ["past", "present", "future"].map((position, index) => ({
    card: {
      id: `major-0${index}-card`,
      arcana: "major" as const,
      suit: null,
      rank: String(index),
      number: index,
      name_en: ["The Fool", "The Magician", "The High Priestess"][index] ?? "Card",
      name_zh: ["愚者", "魔术师", "女祭司"][index] ?? "牌",
      theme: position,
      knowledge: [
        {
          knowledge_id: `arcana:${position}`,
          orientation: "upright" as const,
          locale: "en-US" as const,
          section: "meaning" as const,
          content: `${position} meaning`,
          source: { source_type: "original_synthesis" },
        },
      ],
    },
    position_index: index,
    position_key: position as "past" | "present" | "future",
    position_name_en: position[0]?.toUpperCase() + position.slice(1),
    position_name_zh: ["过去", "现在", "未来"][index] ?? "位置",
    orientation: "upright" as const,
    draw_order: index + 1,
    drawn_at: now,
  }));
  const hasCards = status !== "draft";
  const hasInterpretation = status === "interpreted" || status === "saved";
  return {
    id: READING_ID,
    question: "What deserves my attention?",
    status,
    generation_locale: "en-US",
    spread: {
      key: "past-present-future",
      version: 1,
      name_en: "Past / Present / Future",
      name_zh: "过去 / 现在 / 未来",
      positions: [],
    },
    cards: hasCards ? cards : [],
    interpretation: hasInterpretation
      ? {
          revision: 1,
          source: "fixture_local",
          provider_key: "fixture_local",
          model_id: "fixture-tarot-structured-v1",
          adapter_version: "arcana-fixture-adapter-v1",
          prompt_version: 1,
          input_hash: "a".repeat(64),
          document: {
            schema_version: "tarot-reading.v2",
            generation_locale: "en-US",
            question_restatement: "A restated question for reflection.",
            summary: "A structured summary.",
            positions: cards.map((draw) => ({
              position_key: draw.position_key,
              card_id: draw.card.id,
              orientation: draw.orientation,
              headline: `${draw.position_name_en} · ${draw.card.name_en}`,
              contribution: `${draw.position_name_en} contribution.`,
            })),
            synthesis: "A cross-card synthesis.",
            relationship_analysis: [
              { kind: "relationship", headline: "A relationship", content: "A relationship insight." },
              { kind: "trend", headline: "A trend", content: "A trend insight." },
              { kind: "tension", headline: "A tension", content: "A tension insight." },
              { kind: "turning_point", headline: "A turning point", content: "A turning point insight." },
            ],
            actionable_reflections: ["Test one small action."],
            reflection_prompts: ["What matters now?", "What can change?"],
            knowledge_basis: cards.map((draw) => ({
              card_id: draw.card.id,
              knowledge_id: `arcana:${draw.card.id}:local`,
              source_id: "local-reference",
              source_title: "Local Tarot reference",
              retrieval_mode: "repository_local_only" as const,
            })),
            uncertainty: "Fixture only.",
          },
          retrieved_context: [
            {
              source_id: "local-reference",
              source_title: "Local Tarot reference",
              source_type: "repository_local_corpus",
              repository_reference: "repo://arcana/knowledge/local-reference",
              chunk_id: "arcana:card-1:upright",
              section: "card meaning",
              content: "Bounded local context.",
              retrieval_rationale: "Exact drawn card and orientation.",
              retrieval_score_ppm: 1_000_000,
              locale: "en-US",
              corpus_id: "arcana-tarot-reference",
              corpus_version: "1",
            },
          ],
          citations: [
            {
              source_id: "local-reference",
              chunk_id: "arcana:card-1:upright",
              target_path: "/positions/0",
            },
          ],
          created_at: now,
        }
      : null,
    journal:
      status === "saved"
        ? { personal_interpretation: "My view", notes: "My note", created_at: now, updated_at: now }
        : null,
    created_at: now,
    updated_at: now,
    drawn_at: hasCards ? now : null,
    interpreted_at: hasInterpretation ? now : null,
    saved_at: status === "saved" ? now : null,
  };
}

describe("Arcana core browser flow", () => {
  beforeEach(() => vi.stubGlobal("fetch", vi.fn()));
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("starts, draws, interprets, journals, and exposes a private share preview", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(response(reading("draft")))
      .mockResolvedValueOnce(response(reading("draft")))
      .mockResolvedValueOnce(response(reading("drawn")))
      .mockResolvedValueOnce(response(reading("interpreted")))
      .mockResolvedValueOnce(response(reading("saved")));

    render(
      <MemoryRouter initialEntries={["/arcana"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    await user.type(screen.getByLabelText("Question or focus"), "What deserves my attention?");
    await user.click(screen.getByRole("button", { name: "Prepare reading" }));
    expect(await screen.findByRole("button", { name: "Draw three cards" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Draw three cards" }));
    expect(await screen.findByText("The Fool")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Generate interpretation" }));
    expect(await screen.findByText("A structured summary.")).toBeInTheDocument();
    expect(screen.getByText("Relationship, trend, and turning point")).toBeInTheDocument();
    expect(screen.getByText("A turning point insight.")).toBeInTheDocument();
    expect(screen.getByText("Test one small action.")).toBeInTheDocument();
    expect(screen.getByText("repository_local_only")).toBeInTheDocument();
    expect(screen.getByText("Knowledge citations")).toBeInTheDocument();
    expect(screen.getByText("card meaning · /positions/0")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Your interpretation"), "My view");
    await user.type(screen.getByLabelText("Private notes"), "My note");
    await user.click(screen.getByRole("button", { name: "Save to Journal" }));
    expect(await screen.findByText("Saved to your Journal")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open share preview" })).toHaveAttribute(
      "href",
      `/arcana/readings/${READING_ID}/share`,
    );
    expect(fetchMock).toHaveBeenCalledTimes(5);
  });
});
