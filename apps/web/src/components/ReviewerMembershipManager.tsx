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
  const [state, setState] = useState<MembershipState>({ status: "loading" });
  const [selectedUserId, setSelectedUserId] = useState("");
  const [busyUserId, setBusyUserId] = useState<string | null>(null);
  const [commandError, setCommandError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
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
    setCommandError(null);
    setNotice(null);
    try {
      const assigned = await assignProjectReviewer(projectId, selectedUserId);
      setNotice(`${assigned.display_name} now has reviewer access.`);
      setSelectedUserId("");
      reload();
    } catch {
      setCommandError(
        "Reviewer access was not changed. Refresh the owner-only list and retry.",
      );
    } finally {
      setBusyUserId(null);
    }
  }

  async function remove(membership: ProjectMembership) {
    if (busyUserId !== null) {
      return;
    }
    setBusyUserId(membership.user_id);
    setCommandError(null);
    setNotice(null);
    try {
      await removeProjectReviewer(projectId, membership.user_id);
      setNotice(`${membership.display_name}'s reviewer access was removed.`);
      reload();
    } catch {
      setCommandError(
        "Reviewer access was not changed. Refresh the owner-only list and retry.",
      );
    } finally {
      setBusyUserId(null);
    }
  }

  return (
    <section
      aria-labelledby="reviewer-membership-heading"
      className="project-memberships"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">Owner governed</p>
          <h2 id="reviewer-membership-heading">Reviewer access</h2>
          <p>
            Reviewers can read this project and private images, record image
            readiness, and review submitted region snapshots. They cannot upload,
            edit, submit, or manage access.
          </p>
        </div>
        <button
          className="button button--secondary"
          disabled={state.status === "loading" || busyUserId !== null}
          onClick={reload}
          type="button"
        >
          Refresh access
        </button>
      </div>

      {notice === null ? null : (
        <p className="region-banner region-banner--success" role="status">
          {notice}
        </p>
      )}
      {commandError === null ? null : (
        <p className="region-banner region-banner--error" role="alert">
          {commandError}
        </p>
      )}

      {state.status === "loading" ? (
        <p aria-busy="true" role="status">
          Loading governed memberships…
        </p>
      ) : state.status === "error" ? (
        <p role="alert">
          Owner-only membership data is unavailable. No access change was made.
        </p>
      ) : (
        <>
          <form className="membership-assign" onSubmit={assign}>
            <label htmlFor="reviewer-user">
              Existing signed-in user
              <select
                disabled={busyUserId !== null || state.assignable.length === 0}
                id="reviewer-user"
                onChange={(event) => setSelectedUserId(event.target.value)}
                value={selectedUserId}
              >
                <option value="">Choose a reviewer</option>
                {state.assignable.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.display_name}
                    {user.email === null ? "" : ` · ${user.email}`}
                  </option>
                ))}
              </select>
            </label>
            <button
              className="button button--primary"
              disabled={!selectedUserId || busyUserId !== null}
              type="submit"
            >
              {busyUserId === selectedUserId
                ? "Granting access…"
                : "Grant reviewer access"}
            </button>
          </form>

          {state.assignable.length === 0 ? (
            <p>
              No additional signed-in users are currently eligible. A person must
              complete OIDC sign-in once before the owner can select them here.
            </p>
          ) : null}

          {state.memberships.length === 0 ? (
            <p>No reviewer memberships are assigned.</p>
          ) : (
            <ul className="membership-list">
              {state.memberships.map((membership) => (
                <li key={membership.user_id}>
                  <div>
                    <strong>{membership.display_name}</strong>
                    <span>{membership.email ?? "No email claim"}</span>
                    <small>
                      Reviewer since {formatProjectTimestamp(membership.created_at)}
                    </small>
                  </div>
                  <button
                    className="button button--secondary"
                    disabled={busyUserId !== null}
                    onClick={() => void remove(membership)}
                    type="button"
                  >
                    {busyUserId === membership.user_id
                      ? "Removing…"
                      : "Remove access"}
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
