import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";

import { getTarotSharePreview, type TarotSharePreview } from "../api/arcana";
import { TarotCard } from "../components/TarotCard";
import { useAppTranslation } from "../i18n";

export function ArcanaSharePage() {
  const { readingId } = useParams();
  const { i18n, t } = useAppTranslation();
  const locale = i18n.resolvedLanguage === "zh-CN" ? "zh-CN" : "en-US";
  const [preview, setPreview] = useState<TarotSharePreview | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    if (!readingId) return;
    const controller = new AbortController();
    void getTarotSharePreview(readingId, controller.signal).then(setPreview).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [readingId]);
  if (!preview) return <div className="arcana-page arcana-loading"><h1>{t("arcana.share.heading")}</h1><p>{error ? t("arcana.error") : t("common.loading")}</p></div>;
  return (
    <div className="arcana-page arcana-share-page">
      <header><div><h1>{t("arcana.share.heading")}</h1><p>{t("arcana.share.private")}</p></div><Link to={`/arcana/readings/${preview.reading_id}`}>{t("arcana.share.back")}</Link></header>
      <article className="arcana-share-card">
        <div className="arcana-share-card__title"><span>ARCANA</span><div><h2>{preview.question}</h2><p>{t("arcana.share.cardCopy")}</p></div></div>
        <div className="arcana-share-card__spread">{preview.cards.map((draw) => <TarotCard compact draw={draw} key={draw.position_key} locale={locale} />)}</div>
        <blockquote>{preview.concise_interpretation}</blockquote>
        <footer><span>CreativeDeploy / Arcana</span><span>{t("arcana.share.local")}</span></footer>
      </article>
    </div>
  );
}
