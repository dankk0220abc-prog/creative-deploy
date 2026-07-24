import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import {
  fetchReadiness,
  type ReadinessResponse,
  type ReadinessResult,
} from "../api/health";
import { HealthDashboard } from "../components/HealthDashboard";

const healthyPayload = {
  status: "ok",
  service: "creativedeploy-api",
  version: "0.1.0",
  checks: {
    database: {
      status: "ok",
      latency_ms: 4.25,
      error_code: null,
    },
  },
} satisfies ReadinessResponse;

const degradedPayload = {
  status: "degraded",
  service: "creativedeploy-api",
  version: "0.1.0",
  checks: {
    database: {
      status: "error",
      latency_ms: null,
      error_code: "DATABASE_UNAVAILABLE",
    },
  },
} satisfies ReadinessResponse;

const healthyResult: ReadinessResult = {
  data: healthyPayload,
  httpStatus: 200,
};

const degradedResult: ReadinessResult = {
  data: degradedPayload,
  httpStatus: 503,
};

function responseWith(payload: ReadinessResponse, status: 200 | 503): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

function fetchMock(): ReturnType<typeof vi.fn> {
  return vi.mocked(fetch);
}

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

describe("HealthDashboard", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("shows the initial checking state", () => {
    fetchMock().mockReturnValue(new Promise<Response>(() => undefined));

    render(<HealthDashboard />);

    expect(
      screen.getByRole("status", { name: "FastAPI Service status: Checking" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("status", { name: "PostgreSQL Database status: Checking" }),
    ).toBeInTheDocument();
  });

  it("shows healthy API and database states for a 200 response", async () => {
    fetchMock().mockResolvedValue(responseWith(healthyPayload, 200));

    render(<HealthDashboard />);

    expect(
      await screen.findByRole("status", { name: "FastAPI Service status: Healthy" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("status", { name: "PostgreSQL Database status: Healthy" }),
    ).toBeInTheDocument();
    expect(screen.getByText("DB latency 4.25 ms")).toBeInTheDocument();
  });

  it("keeps the API healthy and marks PostgreSQL unavailable for a 503", async () => {
    fetchMock().mockResolvedValue(responseWith(degradedPayload, 503));

    render(<HealthDashboard />);

    expect(
      await screen.findByRole("status", { name: "FastAPI Service status: Healthy" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("status", {
        name: "PostgreSQL Database status: Unavailable",
      }),
    ).toBeInTheDocument();
  });

  it("marks the API unavailable after a network failure", async () => {
    fetchMock().mockRejectedValue(new TypeError("Network request failed"));

    render(<HealthDashboard />);

    expect(
      await screen.findByRole("status", {
        name: "FastAPI Service status: Unavailable",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("status", { name: "PostgreSQL Database status: Unknown" }),
    ).toBeInTheDocument();
  });

  it("requests health again when Retry is activated", async () => {
    const user = userEvent.setup();
    fetchMock()
      .mockRejectedValueOnce(new TypeError("Network request failed"))
      .mockResolvedValueOnce(responseWith(healthyPayload, 200));

    render(<HealthDashboard />);

    await screen.findByRole("status", {
      name: "FastAPI Service status: Unavailable",
    });
    await user.click(screen.getByRole("button", { name: "Retry check" }));

    expect(
      await screen.findByRole("status", { name: "FastAPI Service status: Healthy" }),
    ).toBeInTheDocument();
    expect(fetchMock()).toHaveBeenCalledTimes(2);
  });

  it("immediately aborts a pending request and starts another on Retry", async () => {
    const user = userEvent.setup();
    const firstRequest = deferred<ReadinessResult>();
    const secondRequest = deferred<ReadinessResult>();
    const readinessFetcher = vi
      .fn<typeof fetchReadiness>()
      .mockReturnValueOnce(firstRequest.promise)
      .mockReturnValueOnce(secondRequest.promise);

    render(<HealthDashboard readinessFetcher={readinessFetcher} />);

    expect(readinessFetcher).toHaveBeenCalledTimes(1);
    const firstSignal = readinessFetcher.mock.calls[0]?.[0];
    expect(firstSignal?.aborted).toBe(false);

    await user.click(screen.getByRole("button", { name: "Retry check" }));

    expect(firstSignal?.aborted).toBe(true);
    expect(readinessFetcher).toHaveBeenCalledTimes(2);
  });

  it("ignores an old request that resolves after the latest healthy response", async () => {
    const user = userEvent.setup();
    const firstRequest = deferred<ReadinessResult>();
    const secondRequest = deferred<ReadinessResult>();
    const readinessFetcher = vi
      .fn<typeof fetchReadiness>()
      .mockReturnValueOnce(firstRequest.promise)
      .mockReturnValueOnce(secondRequest.promise);

    render(<HealthDashboard readinessFetcher={readinessFetcher} />);
    await user.click(screen.getByRole("button", { name: "Retry check" }));

    await act(async () => {
      secondRequest.resolve(healthyResult);
      await secondRequest.promise;
    });
    expect(
      await screen.findByRole("status", { name: "FastAPI Service status: Healthy" }),
    ).toBeInTheDocument();

    await act(async () => {
      firstRequest.resolve(degradedResult);
      await firstRequest.promise;
      await Promise.resolve();
    });

    expect(
      screen.getByRole("status", { name: "FastAPI Service status: Healthy" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("status", { name: "PostgreSQL Database status: Healthy" }),
    ).toBeInTheDocument();
  });

  it("aborts the request on unmount without committing a late result", async () => {
    const pendingRequest = deferred<ReadinessResult>();
    const readinessFetcher = vi
      .fn<typeof fetchReadiness>()
      .mockReturnValue(pendingRequest.promise);
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const { unmount } = render(
      <HealthDashboard readinessFetcher={readinessFetcher} />,
    );
    const signal = readinessFetcher.mock.calls[0]?.[0];

    unmount();

    expect(signal?.aborted).toBe(true);
    await act(async () => {
      pendingRequest.resolve(degradedResult);
      await pendingRequest.promise;
      await Promise.resolve();
    });
    expect(consoleError).not.toHaveBeenCalled();
    expect(
      screen.queryByRole("status", { name: "FastAPI Service status: Unavailable" }),
    ).not.toBeInTheDocument();
  });

  it("reports caller cancellation separately from a network failure", async () => {
    const controller = new AbortController();
    controller.abort();

    await expect(fetchReadiness(controller.signal)).rejects.toMatchObject({
      kind: "caller_aborted",
    });
    expect(fetchMock()).not.toHaveBeenCalled();
  });

  it("reports an internal request timeout separately", async () => {
    vi.useFakeTimers();
    fetchMock().mockImplementation(
      (_input: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener(
            "abort",
            () => reject(new DOMException("Aborted", "AbortError")),
            { once: true },
          );
        }),
    );

    const request = fetchReadiness();
    const expectedRejection = expect(request).rejects.toMatchObject({
      kind: "timeout",
    });
    await vi.advanceTimersByTimeAsync(5_000);
    await expectedRejection;
  });

  it("states that PaintPilot product features are not implemented", () => {
    fetchMock().mockReturnValue(new Promise<Response>(() => undefined));

    render(<App />);

    expect(
      screen.getByText(
        "Foundation connectivity check only. PaintPilot features are not implemented yet.",
      ),
    ).toBeInTheDocument();
  });
});
