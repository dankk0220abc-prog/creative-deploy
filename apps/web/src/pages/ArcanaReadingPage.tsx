import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";

import { drawTarotReading, getTarotReading, interpretTarotReading, saveTarotJournal, type TarotReading } from "../api/arcana";
import { TarotCard } from "../components/TarotCard";
import { useAppTranslation } from "../i18n";

export function ArcanaReadingPage() {
  const { readingId } = useParams();
  const { i18n, t } = useAppTranslation();
  const locale = i18n.resolvedLanguage === "zh-CN" ? "zh-CN" : "en-US";
  const [reading, setReading] = useState<TarotReading | null>(null);
  const [personal, setPersonal] = useState("");
  const [notes, setNotes] = useState("");
  const [pending, setPending] = useState<"draw" | "interpret" | "save" | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!readingId) return;
    const controller = new AbortController();
    void getTarotReading(readingId, controller.signal)
      .then((value) => {
        setReading(value);
        setPersonal(value.journal?.personal_interpretation ?? "");
        setNotes(value.journal?.notes ?? "");
      })
      .catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [readingId]);

  const command = async (kind: "draw" | "interpret" | "save") => {
    if (!readingId || pending) return;
    setPending(kind);
    setError(false);
    try {
      const value = kind === "draw"
        ? await drawTarotReading(readingId)
        : kind === "interpret"
          ? await interpretTarotReading(readingId)
          : await saveTarotJournal(readingId, personal, notes);
      setReading(value);
      setPending(null);
    } catch {
      setError(true);
      setPending(null);
    }
  };

  if (!reading) {
    return <div className="arcana-page arcana-loading"><h1>{t("arcana.reading.loading")}</h1>{error ? <p role="alert">{t("arcana.error")}</p> : null}</div>;
  }

  return (
    <div className="arcana-page arcana-reading">
      <header className="arcana-reading__header">
        <div><h1>{reading.question}</h1><p>{t("arcana.reading.spreadVersion", { version: reading.spread.version })}</p></div>
        <span className="arcana-reading__status">{t(`arcana.status.${reading.status}`)}</span>
      </header>

      <section className="arcana-table" aria-label={t("arcana.reading.cardsLabel")}>
        {reading.cards.length === 0 ? (
          <div className="arcana-table__unopened">
            <div className="arcana-card-backs" aria-hidden="true"><i /><i /><i /></div>
            <h2>{t("arcana.reading.ready")}</h2>
            <p>{t("arcana.reading.readyCopy")}</p>
            <button className="arcana-action" disabled={pending !== null} onClick={() => void command("draw")} type="button">{pending === "draw" ? t("arcana.reading.drawing") : t("arcana.reading.draw")}</button>
          </div>
        ) : (
          <div className="tarot-spread">{reading.cards.map((draw) => <TarotCard draw={draw} key={draw.position_key} locale={locale} />)}</div>
        )}
      </section>

      {reading.cards.length === 3 && !reading.interpretation ? (
        <section className="arcana-next-step">
          <div><h2>{t("arcana.interpret.ready")}</h2><p>{t("arcana.interpret.fixture")}</p></div>
          <button className="arcana-action" disabled={pending !== null} onClick={() => void command("interpret")} type="button">{pending === "interpret" ? t("arcana.interpret.generating") : t("arcana.interpret.generate")}</button>
        </section>
      ) : null}

      {reading.interpretation ? (
        <section className="arcana-interpretation">
          <header><h2>{t("arcana.interpret.heading")}</h2><div><p className="arcana-interpretation__question">{reading.interpretation.document.question_restatement}</p><p>{reading.interpretation.document.summary}</p></div></header>
          <div className="arcana-interpretation__positions">
            {reading.interpretation.document.positions.map((position) => <article key={position.position_key}><h3>{position.headline}</h3><p>{position.contribution}</p></article>)}
          </div>
          <div className="arcana-synthesis"><h3>{t("arcana.interpret.synthesis")}</h3><p>{reading.interpretation.document.synthesis}</p></div>
          <section className="arcana-relationships" aria-label={t("arcana.interpret.relationships")}>
            <h3>{t("arcana.interpret.relationships")}</h3>
            <div>{reading.interpretation.document.relationship_analysis.map((insight) => <article key={insight.kind}><span>{t(`arcana.interpret.kind.${insight.kind}`)}</span><h4>{insight.headline}</h4><p>{insight.content}</p></article>)}</div>
          </section>
          <section className="arcana-actions"><h3>{t("arcana.interpret.actions")}</h3><ol>{reading.interpretation.document.actionable_reflections.map((action) => <li key={action}>{action}</li>)}</ol></section>
          <div className="arcana-reflections"><h3>{t("arcana.interpret.reflect")}</h3><ul>{reading.interpretation.document.reflection_prompts.map((prompt) => <li key={prompt}>{prompt}</li>)}</ul></div>
          <details className="arcana-provenance">
            <summary>{t("arcana.interpret.details")}</summary>
            <p>{reading.interpretation.document.uncertainty}</p>
            <dl>
              <div><dt>{t("arcana.interpret.provenance.source")}</dt><dd>{reading.interpretation.document.knowledge_basis[0]?.source_title}</dd></div>
              <div><dt>{t("arcana.interpret.provenance.retrieval")}</dt><dd>{reading.interpretation.document.knowledge_basis[0]?.retrieval_mode}</dd></div>
              <div><dt>{t("arcana.interpret.provenance.schema")}</dt><dd>{reading.interpretation.document.schema_version}</dd></div>
            </dl>
            {reading.interpretation.citations.length > 0 ? (
              <section aria-label={t("arcana.interpret.citations")}>
                <h3>{t("arcana.interpret.citations")}</h3>
                <p>{t("arcana.interpret.citationsCopy")}</p>
                <ul>
                  {reading.interpretation.citations.map((citation) => {
                    const source = reading.interpretation?.retrieved_context.find(
                      (item) => item.source_id === citation.source_id && item.chunk_id === citation.chunk_id,
                    );
                    return (
                      <li key={`${citation.source_id}:${citation.chunk_id}:${citation.target_path}`}>
                        <strong>{source?.source_title ?? citation.source_id}</strong>
                        <span>{source?.section ?? citation.chunk_id} · {citation.target_path}</span>
                      </li>
                    );
                  })}
                </ul>
              </section>
            ) : null}
          </details>
        </section>
      ) : null}

      {reading.interpretation ? (
        <section className="arcana-journal">
          <header><h2>{t("arcana.journal.heading")}</h2><p>{t("arcana.journal.copy")}</p></header>
          <div className="arcana-journal__fields">
            <label>{t("arcana.journal.personal")}<textarea maxLength={4000} onChange={(event) => setPersonal(event.target.value)} rows={5} value={personal} /></label>
            <label>{t("arcana.journal.notes")}<textarea maxLength={8000} onChange={(event) => setNotes(event.target.value)} rows={5} value={notes} /></label>
          </div>
          <div className="arcana-journal__actions">
            <button className="arcana-action" disabled={pending !== null} onClick={() => void command("save")} type="button">{pending === "save" ? t("arcana.journal.saving") : t("arcana.journal.save")}</button>
            {reading.status === "saved" ? <><span role="status">{t("arcana.journal.saved")}</span><Link to={`/arcana/readings/${reading.id}/share`}>{t("arcana.share.open")}</Link></> : null}
          </div>
        </section>
      ) : null}
      {error ? <p className="arcana-error" role="alert">{t("arcana.error")}</p> : null}
    </div>
  );
}
