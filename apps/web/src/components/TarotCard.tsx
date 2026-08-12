import type { TarotDraw } from "../api/arcana";

interface TarotCardProps {
  draw: TarotDraw;
  locale: "en-US" | "zh-CN";
  compact?: boolean;
}

export function TarotCard({ draw, locale, compact = false }: TarotCardProps) {
  const name = locale === "zh-CN" ? draw.card.name_zh : draw.card.name_en;
  const position = locale === "zh-CN" ? draw.position_name_zh : draw.position_name_en;
  const meaning = draw.card.knowledge.find(
    (entry) => entry.locale === locale && entry.orientation === draw.orientation,
  )?.content;

  return (
    <article className={`tarot-card${compact ? " tarot-card--compact" : ""}${draw.orientation === "reversed" ? " tarot-card--reversed" : ""}`}>
      <div className="tarot-card__position">{position}</div>
      <div aria-hidden="true" className="tarot-card__face">
        <span className="tarot-card__index">{draw.card.arcana === "major" ? String(draw.card.number).padStart(2, "0") : draw.card.rank.slice(0, 2).toUpperCase()}</span>
        <span className="tarot-card__geometry"><i /><i /><i /></span>
        <span className="tarot-card__suit">{draw.card.suit?.slice(0, 1).toUpperCase() ?? "A"}</span>
      </div>
      <div className="tarot-card__copy">
        <h3>{name}</h3>
        <span>{draw.orientation === "upright" ? (locale === "zh-CN" ? "正位" : "Upright") : (locale === "zh-CN" ? "逆位" : "Reversed")}</span>
        {!compact && meaning ? <p>{meaning}</p> : null}
      </div>
    </article>
  );
}
