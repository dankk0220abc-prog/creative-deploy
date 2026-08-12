import { useEffect, useState } from "react";
import { Link } from "react-router";

import { listTarotReadings, type TarotReading } from "../api/arcana";
import { useAppTranslation } from "../i18n";

export function ArcanaHistoryPage() {
  const { t } = useAppTranslation();
  const [items, setItems] = useState<TarotReading[] | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    void listTarotReadings(controller.signal).then(setItems).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, []);
  return (
    <div className="arcana-page arcana-history">
      <header><h1>{t("arcana.history.heading")}</h1><p>{t("arcana.history.copy")}</p><Link className="arcana-history__new" to="/arcana">{t("arcana.history.new")}</Link></header>
      {error ? <p className="arcana-error" role="alert">{t("arcana.error")}</p> : null}
      {items === null ? <p>{t("common.loading")}</p> : items.length === 0 ? <div className="arcana-history__empty"><p>{t("arcana.history.empty")}</p><Link className="arcana-action" to="/arcana">{t("arcana.start.begin")}</Link></div> : (
        <ol className="arcana-history__list">{items.map((reading) => <li key={reading.id}><Link to={`/arcana/readings/${reading.id}`}><div><span>{t(`arcana.status.${reading.status}`)}</span><h2>{reading.question}</h2><p>{reading.spread.name_en} · {new Date(reading.created_at).toLocaleDateString()}</p></div><strong>{t("arcana.history.reopen")}</strong></Link></li>)}</ol>
      )}
    </div>
  );
}
