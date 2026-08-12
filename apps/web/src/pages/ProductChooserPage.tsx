import { Link } from "react-router";

import { useAppTranslation } from "../i18n";

export function ProductChooserPage() {
  const { t } = useAppTranslation();
  return (
    <div className="product-chooser">
      <header>
        <span>CreativeDeploy</span>
        <h1>{t("products.heading")}</h1>
        <p>{t("products.copy")}</p>
      </header>
      <div className="product-chooser__rail">
        <Link className="product-space product-space--paint" to="/paintpilot/projects">
          <span className="product-space__mark">P</span>
          <div><h2>PaintPilot</h2><p>{t("products.paintCopy")}</p></div>
          <strong>{t("products.open")}</strong>
        </Link>
        <Link className="product-space product-space--arcana" to="/arcana">
          <span className="product-space__mark"><span aria-hidden="true" className="product-space__sigil">A</span></span>
          <div><h2>Arcana</h2><p>{t("products.arcanaCopy")}</p></div>
          <strong>{t("products.open")}</strong>
        </Link>
      </div>
    </div>
  );
}
