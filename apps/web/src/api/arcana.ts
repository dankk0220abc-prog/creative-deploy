import { fetchWithCsrf } from "./auth";

export type ArcanaLocale = "en-US" | "zh-CN";
export type TarotOrientation = "upright" | "reversed";
export type TarotReadingStatus = "draft" | "drawn" | "interpreted" | "saved";

export interface TarotKnowledge {
  knowledge_id: string;
  orientation: TarotOrientation;
  locale: ArcanaLocale;
  section: "meaning" | "element" | "number" | "court_role" | "position" | "spread_rule";
  content: string;
  source: Record<string, unknown>;
}

export interface TarotCard {
  id: string;
  arcana: "major" | "minor";
  suit: string | null;
  rank: string;
  number: number;
  name_en: string;
  name_zh: string;
  theme: string;
  knowledge: TarotKnowledge[];
}

export interface TarotDraw {
  card: TarotCard;
  position_index: number;
  position_key: "past" | "present" | "future";
  position_name_en: string;
  position_name_zh: string;
  orientation: TarotOrientation;
  draw_order: number;
  drawn_at: string;
}

export interface TarotPositionInterpretation {
  position_key: "past" | "present" | "future";
  card_id: string;
  orientation: TarotOrientation;
  headline: string;
  contribution: string;
}

export interface TarotRetrievedContext {
  source_id: string;
  source_title: string;
  source_type: string;
  repository_reference: string;
  chunk_id: string;
  section: string;
  content: string;
  retrieval_rationale: string;
  retrieval_score_ppm: number | null;
  locale: ArcanaLocale;
  corpus_id: string;
  corpus_version: string;
}

export interface TarotCitation {
  source_id: string;
  chunk_id: string;
  target_path: string;
}

export interface TarotInterpretation {
  revision: number;
  source: "fixture_local" | "zhipu_live" | "user_edit";
  provider_key: string;
  model_id: string;
  adapter_version: string;
  prompt_version: number;
  input_hash: string;
  document: {
    schema_version: "tarot-reading.v2";
    generation_locale: ArcanaLocale;
    question_restatement: string;
    summary: string;
    positions: TarotPositionInterpretation[];
    synthesis: string;
    relationship_analysis: Array<{
      kind: "relationship" | "trend" | "tension" | "turning_point";
      headline: string;
      content: string;
    }>;
    actionable_reflections: string[];
    reflection_prompts: string[];
    knowledge_basis: Array<{
      card_id: string;
      knowledge_id: string;
      source_id: string;
      source_title: string;
      retrieval_mode: "repository_local_only";
    }>;
    uncertainty: string;
  };
  retrieved_context: TarotRetrievedContext[];
  citations: TarotCitation[];
  created_at: string;
}

export interface TarotReading {
  id: string;
  question: string;
  status: TarotReadingStatus;
  generation_locale: ArcanaLocale;
  spread: {
    key: "past-present-future";
    version: 1;
    name_en: string;
    name_zh: string;
    positions: Array<{ key: string; name_en: string; name_zh: string }>;
  };
  cards: TarotDraw[];
  interpretation: TarotInterpretation | null;
  journal: {
    personal_interpretation: string;
    notes: string;
    created_at: string;
    updated_at: string;
  } | null;
  created_at: string;
  updated_at: string;
  drawn_at: string | null;
  interpreted_at: string | null;
  saved_at: string | null;
}

export interface TarotSharePreview {
  reading_id: string;
  question: string;
  generation_locale: ArcanaLocale;
  cards: TarotDraw[];
  concise_interpretation: string;
  private_local_preview: true;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isReading(value: unknown): value is TarotReading {
  return (
    isObject(value) &&
    typeof value.id === "string" &&
    typeof value.question === "string" &&
    ["draft", "drawn", "interpreted", "saved"].includes(String(value.status)) &&
    (value.generation_locale === "en-US" || value.generation_locale === "zh-CN") &&
    Array.isArray(value.cards) &&
    isObject(value.spread) &&
    (value.interpretation === null || isObject(value.interpretation)) &&
    (value.journal === null || isObject(value.journal))
  );
}

async function jsonRequest(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetchWithCsrf(path, {
    ...init,
    headers: { Accept: "application/json", "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    throw new Error(`arcana_http_${response.status}`);
  }
  return response.json();
}

function requireReading(value: unknown): TarotReading {
  if (!isReading(value)) {
    throw new Error("arcana_invalid_reading");
  }
  return value;
}

export async function createTarotReading(question: string, generationLocale: ArcanaLocale): Promise<TarotReading> {
  return requireReading(
    await jsonRequest("/api/v1/arcana/readings", {
      method: "POST",
      body: JSON.stringify({ question, generation_locale: generationLocale }),
    }),
  );
}

export async function getTarotReading(readingId: string, signal?: AbortSignal): Promise<TarotReading> {
  return requireReading(await jsonRequest(`/api/v1/arcana/readings/${readingId}`, { signal }));
}

export async function drawTarotReading(readingId: string): Promise<TarotReading> {
  return requireReading(await jsonRequest(`/api/v1/arcana/readings/${readingId}/draw`, { method: "POST" }));
}

export async function interpretTarotReading(readingId: string): Promise<TarotReading> {
  return requireReading(await jsonRequest(`/api/v1/arcana/readings/${readingId}/interpret`, { method: "POST" }));
}

export async function saveTarotJournal(readingId: string, personalInterpretation: string, notes: string): Promise<TarotReading> {
  return requireReading(
    await jsonRequest(`/api/v1/arcana/readings/${readingId}/journal`, {
      method: "PUT",
      body: JSON.stringify({ personal_interpretation: personalInterpretation, notes }),
    }),
  );
}

export async function listTarotReadings(signal?: AbortSignal): Promise<TarotReading[]> {
  const value = await jsonRequest("/api/v1/arcana/readings", { signal });
  if (!isObject(value) || !Array.isArray(value.items) || !value.items.every(isReading)) {
    throw new Error("arcana_invalid_history");
  }
  return value.items;
}

export async function getTarotSharePreview(readingId: string, signal?: AbortSignal): Promise<TarotSharePreview> {
  const value = await jsonRequest(`/api/v1/arcana/readings/${readingId}/share-preview`, { signal });
  if (!isObject(value) || value.private_local_preview !== true || !Array.isArray(value.cards)) {
    throw new Error("arcana_invalid_share_preview");
  }
  return value as unknown as TarotSharePreview;
}
