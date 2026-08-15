import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router";

import { createTarotReading } from "../api/arcana";
import { useAppTranslation } from "../i18n";

export function ArcanaPage() {
  const { i18n, t } = useAppTranslation();
  const navigate = useNavigate();
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);
  const locale = i18n.resolvedLanguage === "zh-CN" ? "zh-CN" : "en-US";
  const isPublicDemo = import.meta.env.VITE_RUNTIME_PROFILE === "public-demo";

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!question.trim() || pending) return;
    setPending(true);
    setError(false);
    try {
      const reading = await createTarotReading(question, locale);
      await navigate(`/arcana/readings/${reading.id}`);
    } catch {
      setError(true);
      setPending(false);
    }
  };

  return (
    <div className="arcana-page arcana-start">
      <section className="arcana-start__stage">
        <div aria-hidden="true" className="arcana-start__constellation"><i /><i /><i /></div>
        <div className="arcana-start__copy">
          <h1>{t("arcana.start.heading")}</h1>
          <p>{t("arcana.start.copy")}</p>
          <p className="arcana-start__ritual">{t("arcana.start.ritual")}</p>
        </div>
        {isPublicDemo ? (
          <div className="arcana-question">
            <p>{t("arcana.demo.readOnly")}</p>
            <Link className="arcana-action" to="/arcana/journal">{t("arcana.demo.openReading")}</Link>
          </div>
        ) : (
          <form className="arcana-question" onSubmit={(event) => void submit(event)}>
            <label htmlFor="arcana-question">{t("arcana.start.question")}</label>
            <textarea id="arcana-question" maxLength={500} onChange={(event) => setQuestion(event.target.value)} placeholder={t("arcana.start.placeholder")} rows={4} value={question} />
            <div className="arcana-question__spread">
              <span>{t("arcana.start.spread")}</span>
              <strong>{t("arcana.spread.name")}</strong>
              <small>{t("arcana.spread.positions")}</small>
            </div>
            {error ? <p className="arcana-error" role="alert">{t("arcana.error")}</p> : null}
            <button className="arcana-action" disabled={!question.trim() || pending} type="submit">{pending ? t("arcana.start.preparing") : t("arcana.start.begin")}</button>
          </form>
        )}
      </section>
      <aside className="arcana-start__archive">
        <div className="arcana-deck-stack" aria-hidden="true"><i /><i /><i /></div>
        <div><h2>{t("arcana.start.archiveHeading")}</h2><p>{t("arcana.start.boundary")}</p></div>
      </aside>
    </div>
  );
}
