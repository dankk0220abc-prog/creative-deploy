import { type FormEvent, useCallback, useEffect, useState } from "react";

import {
  assignProjectReviewer,
  listAssignableReviewers,
  listProjectMemberships,
  type MembershipUser,
  type ProjectMembership,
  removeProjectReviewer,
} from "../api/memberships";
import { formatProjectTimestamp } from "../utils/format";
import { useAppTranslation } from "../i18n";

interface ReviewerMembershipManagerProps {
  projectId: string;
}

type MembershipState =
  | {
      status: "loaded";
      assignable: MembershipUser[];
      memberships: ProjectMembership[];
    }
  | { status: "loading" }
  | { status: "error" };

export function ReviewerMembershipManager({
  projectId,
}: ReviewerMembershipManagerProps) {
  const { t } = useAppTranslation();
  const [state, setState] = useState<MembershipState>({ status: "loading" });
  const [selectedUserId, setSelectedUserId] = useState("");
  const [busyUserId, setBusyUserId] = useState<string | null>(null);
  const [commandError, setCommandError] = useState(false);
  const [notice, setNotice] = useState<{ key: string; name: string } | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const reload = useCallback(() => {
    setState({ status: "loading" });
    setReloadToken((current) => current + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      listProjectMemberships(projectId, controller.signal),
      listAssignableReviewers(projectId, controller.signal),
    ])
      .then(([memberships, assignable]) => {
        if (!controller.signal.aborted) {
          setState({ status: "loaded", memberships, assignable });
          setSelectedUserId((current) =>
            assignable.some((user) => user.id === current) ? current : "",
          );
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setState({ status: "error" });
        }
      });
    return () => controller.abort();
  }, [projectId, reloadToken]);

  async function assign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedUserId || busyUserId !== null) {
      return;
    }
    setBusyUserId(selectedUserId);
    setCommandError(false);
    setNotice(null);
    try {
      const assigned = await assignProjectReviewer(projectId, selectedUserId);
      setNotice({ key: "membership.granted", name: assigned.display_name });
      setSelectedUserId("");
      reload();
    } catch {
      setCommandError(true);
    } finally {
      setBusyUserId(null);
    }
  }

  async function remove(membership: ProjectMembership) {
    if (busyUserId !== null) {
      return;
    }
    setBusyUserId(membership.user_id);
    setCommandError(false);
    setNotice(null);
    try {
      await removeProjectReviewer(projectId, membership.user_id);
      setNotice({ key: "membership.removed", name: membership.display_name });
      reload();
    } catch {
      setCommandError(true);
    } finally {
      setBusyUserId(null);
    }
  }

  return (
    <section
      aria-labelledby="reviewer-membership-heading"
      className="project-memberships"
      id="reviewer-access"
    >
      <div className="section-heading">
        <div>
          <p className="context-label">{t("membership.eyebrow")}</p>
          <h2 id="reviewer-membership-heading">{t("membership.heading")}</h2>
          <p>{t("membership.copy")}</p>
        </div>
        <button
          aria-busy={state.status === "loading"}
          className="button button--secondary"
          disabled={state.status === "loading" || busyUserId !== null}
          onClick={reload}
          type="button"
        >
          {t("membership.refresh")}
        </button>
      </div>

      {notice === null ? null : (
        <p className="region-banner region-banner--success" role="status">
          {t(notice.key, { name: notice.name })}
        </p>
      )}
      {!commandError ? null : (
        <p className="region-banner region-banner--error" role="alert">
          {t("membership.commandError")}
        </p>
      )}

      {state.status === "loading" ? (
        <p aria-busy="true" role="status">
          {t("membership.loading")}
        </p>
      ) : state.status === "error" ? (
        <p role="alert">
          {t("membership.unavailable")}
        </p>
      ) : (
        <>
          <form className="membership-assign" onSubmit={assign}>
            <label htmlFor="reviewer-user">
              {t("membership.userLabel")}
              <select
                aria-describedby="reviewer-user-help"
                disabled={busyUserId !== null || state.assignable.length === 0}
                id="reviewer-user"
                onChange={(event) => setSelectedUserId(event.target.value)}
                value={selectedUserId}
              >
                <option value="">{t("membership.choose")}</option>
                {state.assignable.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.display_name}
                    {user.email === null ? "" : ` · ${user.email}`}
                  </option>
                ))}
              </select>
              <span className="control-help" id="reviewer-user-help">
                {t("membership.userHelp")}
              </span>
            </label>
            <button
              aria-busy={busyUserId === selectedUserId && selectedUserId !== ""}
              className="button button--primary"
              disabled={!selectedUserId || busyUserId !== null}
              type="submit"
            >
              {busyUserId === selectedUserId
                ? t("membership.granting")
                : t("membership.grant")}
            </button>
          </form>

          {state.assignable.length === 0 ? (
            <p>{t("membership.noEligible")}</p>
          ) : null}

          {state.memberships.length === 0 ? (
            <p>{t("membership.empty")}</p>
          ) : (
            <ul className="membership-list">
              {state.memberships.map((membership) => (
                <li key={membership.user_id}>
                  <div>
                    <strong>{membership.display_name}</strong>
                    <span>{membership.email ?? t("membership.noEmail")}</span>
                    <small>
                      {t("membership.since", { date: formatProjectTimestamp(membership.created_at) })}
                    </small>
                  </div>
                  <button
                    aria-busy={busyUserId === membership.user_id}
                    className="button button--secondary"
                    disabled={busyUserId !== null}
                    onClick={() => void remove(membership)}
                    type="button"
                  >
                    {busyUserId === membership.user_id
                      ? t("membership.removing")
                      : t("membership.remove")}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
