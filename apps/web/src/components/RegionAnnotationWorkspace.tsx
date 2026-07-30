import {
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  type WheelEvent,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  createRegionIdempotencyKey,
  createRegionSetReview,
  forkRegionSetDraft,
  getRegionSet,
  getRegionWorkbench,
  type RegionDraftInput,
  type RegionSet,
  RegionSetApiError,
  saveRegionSet,
  submitRegionSet,
  type RegionWorkbench,
} from "../api/regionSets";
import {
  persistedRegionsToDrafts,
  validateRegionDrafts,
} from "../utils/regionGeometry";
import { formatProjectTimestamp } from "../utils/format";
import { FeedbackPanel } from "./FeedbackPanel";

const PPM_MAX = 1_000_000;
const defaultViewBox = { x: 0, y: 0, width: PPM_MAX, height: PPM_MAX };
const regionColors = [
  "#63b3a6",
  "#d2a45f",
  "#de7d83",
  "#83a9e8",
  "#c390dc",
  "#8bc474",
];

interface RegionAnnotationWorkspaceProps {
  onViewStateChange?: (
    state: "current" | "error" | "historical" | "loading" | "not_found",
  ) => void;
  projectId: string;
}

interface CommandAttempt {
  fingerprint: string;
  key: string;
}

interface Point {
  x_ppm: number;
  y_ppm: number;
}

type Tool = "draw" | "edit" | "pan";
type LoadState =
  | { status: "error"; error: RegionSetApiError }
  | { status: "loaded"; workbench: RegionWorkbench }
  | { status: "loading" };

interface RegionCommandTargets {
  fork:
    | {
        current: RegionSet;
        source: RegionSet;
      }
    | null;
  isViewingHistoricalSnapshot: boolean;
  lifecycle: RegionSet | null;
}

function regionCommandTargets(
  currentRegionSet: RegionSet | null,
  viewedRegionSet: RegionSet | null,
): RegionCommandTargets {
  if (currentRegionSet === null || viewedRegionSet === null) {
    return {
      fork: null,
      isViewingHistoricalSnapshot: false,
      lifecycle: null,
    };
  }
  if (currentRegionSet.id === viewedRegionSet.id) {
    return {
      fork: null,
      isViewingHistoricalSnapshot: false,
      lifecycle: viewedRegionSet,
    };
  }
  return {
    fork: { current: currentRegionSet, source: viewedRegionSet },
    isViewingHistoricalSnapshot: true,
    lifecycle: null,
  };
}

function apiError(error: unknown): RegionSetApiError {
  return error instanceof RegionSetApiError
    ? error
    : new RegionSetApiError(
        "internal",
        "The region workbench could not complete the request safely.",
      );
}

function commandMessage(error: RegionSetApiError): string {
  if (error.kind === "network") {
    return "The connection was interrupted. Retry keeps the same protected command.";
  }
  if (error.kind === "conflict") {
    return "The image set or region snapshot changed. Reload before reapplying edits.";
  }
  if (error.kind === "validation") {
    return "The command does not meet the current geometry or lifecycle contract.";
  }
  if (error.kind === "not_found") {
    return "This project or snapshot is not available to the current operator.";
  }
  return "The region service returned an incomplete or unexpected response.";
}

function snapshotFingerprint(regions: RegionDraftInput[]): string {
  return JSON.stringify(regions);
}

function makeRegion(vertices: Point[], zIndex: number): RegionDraftInput {
  return {
    stable_region_key: crypto.randomUUID(),
    kind: "paint",
    label: `Region ${zIndex + 1}`,
    z_index: zIndex,
    opacity_ppm: 500_000,
    notes: null,
    vertices,
  };
}

function exactPoint(
  event: Pick<ReactPointerEvent<SVGSVGElement>, "clientX" | "clientY">,
  svg: SVGSVGElement,
): Point | null {
  const screenTransform = svg.getScreenCTM();
  if (screenTransform === null) {
    return null;
  }
  const screenPoint = svg.createSVGPoint();
  screenPoint.x = event.clientX;
  screenPoint.y = event.clientY;
  const canvasPoint = screenPoint.matrixTransform(screenTransform.inverse());
  if (!Number.isFinite(canvasPoint.x) || !Number.isFinite(canvasPoint.y)) {
    return null;
  }
  return {
    x_ppm: Math.max(0, Math.min(PPM_MAX, Math.round(canvasPoint.x))),
    y_ppm: Math.max(0, Math.min(PPM_MAX, Math.round(canvasPoint.y))),
  };
}

function isInteractiveCanvasTarget(
  target: EventTarget | null,
  svg: SVGSVGElement,
): boolean {
  return (
    target !== svg &&
    target instanceof Element &&
    target.closest('[data-region-interactive="true"]') !== null
  );
}

export function RegionAnnotationWorkspace({
  onViewStateChange,
  projectId,
}: RegionAnnotationWorkspaceProps) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [viewedRegionSet, setViewedRegionSet] = useState<RegionSet | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [regions, setRegions] = useState<RegionDraftInput[]>([]);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [selectedVertex, setSelectedVertex] = useState<number | null>(null);
  const [hiddenKeys, setHiddenKeys] = useState<Set<string>>(new Set());
  const [drawing, setDrawing] = useState<Point[]>([]);
  const [tool, setTool] = useState<Tool>("edit");
  const [editable, setEditable] = useState(false);
  const [viewBox, setViewBox] = useState(defaultViewBox);
  const [undoStack, setUndoStack] = useState<string[]>([]);
  const [redoStack, setRedoStack] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [commandError, setCommandError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reviewReason, setReviewReason] = useState("");
  const [draggingVertex, setDraggingVertex] = useState<{
    key: string;
    index: number;
  } | null>(null);
  const [panStart, setPanStart] = useState<{
    clientX: number;
    clientY: number;
    viewBox: typeof defaultViewBox;
  } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const dragStartSnapshotRef = useRef<string | null>(null);
  const commandAttemptRef = useRef<Record<string, CommandAttempt>>({});

  const load = useCallback(() => {
    setState({ status: "loading" });
    setReloadToken((current) => current + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void getRegionWorkbench(projectId, controller.signal)
      .then((workbench) => {
        if (controller.signal.aborted) {
          return;
        }
        const current = workbench.current_region_set;
        setState({ status: "loaded", workbench });
        setViewedRegionSet(current);
        setRegions(
          current === null ? [] : persistedRegionsToDrafts(current.regions),
        );
        setSelectedKey(current?.regions[0]?.stable_region_key ?? null);
        setSelectedVertex(null);
        setEditable(
          current === null
            ? workbench.can_create_draft
            : current.effective_lifecycle === "draft" && !current.stale,
        );
        setDrawing([]);
        setUndoStack([]);
        setRedoStack([]);
        setCommandError(null);
        setNotice(null);
        setViewBox(defaultViewBox);
      })
      .catch((error: unknown) => {
        const resolved = apiError(error);
        if (!controller.signal.aborted && resolved.kind !== "aborted") {
          setState({ status: "error", error: resolved });
        }
      });
    return () => controller.abort();
  }, [projectId, reloadToken]);

  const workbench = state.status === "loaded" ? state.workbench : null;
  const currentRegionSet = workbench?.current_region_set ?? null;
  const commandTargets = useMemo(
    () => regionCommandTargets(currentRegionSet, viewedRegionSet),
    [currentRegionSet, viewedRegionSet],
  );
  const selected = useMemo(
    () => regions.find((region) => region.stable_region_key === selectedKey) ?? null,
    [regions, selectedKey],
  );
  const selectedIndex = useMemo(
    () =>
      selectedKey === null
        ? -1
        : regions.findIndex((region) => region.stable_region_key === selectedKey),
    [regions, selectedKey],
  );
  const geometryErrors = useMemo(() => validateRegionDrafts(regions), [regions]);

  useLayoutEffect(() => {
    if (state.status === "loaded" && headingRef.current !== null) {
      headingRef.current.tabIndex = -1;
      headingRef.current.focus({ preventScroll: true });
    }
  }, [state.status]);

  useLayoutEffect(() => {
    if (state.status === "loading" || (currentRegionSet !== null && viewedRegionSet === null)) {
      onViewStateChange?.("loading");
      return;
    }
    if (state.status === "error") {
      onViewStateChange?.(
        state.error.kind === "not_found" ? "not_found" : "error",
      );
      return;
    }
    if (
      workbench === null ||
      workbench.source_content_url === null ||
      workbench.source_image_width === null ||
      workbench.source_image_height === null
    ) {
      onViewStateChange?.("error");
      return;
    }
    onViewStateChange?.(
      commandTargets.isViewingHistoricalSnapshot ? "historical" : "current",
    );
  }, [
    commandTargets.isViewingHistoricalSnapshot,
    currentRegionSet,
    onViewStateChange,
    state,
    viewedRegionSet,
    workbench,
  ]);

  const commitRegions = useCallback(
    (next: RegionDraftInput[]) => {
      setUndoStack((stack) => [...stack.slice(-49), snapshotFingerprint(regions)]);
      setRedoStack([]);
      setRegions(next);
      setCommandError(null);
      setNotice(null);
    },
    [regions],
  );

  const updateSelected = useCallback(
    (transform: (region: RegionDraftInput) => RegionDraftInput) => {
      if (selectedKey === null) {
        return;
      }
      commitRegions(
        regions.map((region) =>
          region.stable_region_key === selectedKey ? transform(region) : region,
        ),
      );
    },
    [commitRegions, regions, selectedKey],
  );

  const undo = useCallback(() => {
    const previous = undoStack.at(-1);
    if (previous === undefined) {
      return;
    }
    setRedoStack((stack) => [...stack, snapshotFingerprint(regions)]);
    setUndoStack((stack) => stack.slice(0, -1));
    setRegions(JSON.parse(previous) as RegionDraftInput[]);
  }, [regions, undoStack]);

  const redo = useCallback(() => {
    const next = redoStack.at(-1);
    if (next === undefined) {
      return;
    }
    setUndoStack((stack) => [...stack, snapshotFingerprint(regions)]);
    setRedoStack((stack) => stack.slice(0, -1));
    setRegions(JSON.parse(next) as RegionDraftInput[]);
  }, [redoStack, regions]);

  useEffect(() => {
    function handleKeyboard(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setDrawing([]);
        setDraggingVertex(null);
        return;
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        if (event.shiftKey) {
          redo();
        } else {
          undo();
        }
      }
    }
    window.addEventListener("keydown", handleKeyboard);
    return () => window.removeEventListener("keydown", handleKeyboard);
  }, [redo, undo]);

  function commandKey(name: string, fingerprint: string): string {
    const current = commandAttemptRef.current[name];
    if (current === undefined || current.fingerprint !== fingerprint) {
      const next = { fingerprint, key: createRegionIdempotencyKey() };
      commandAttemptRef.current[name] = next;
      return next.key;
    }
    return current.key;
  }

  function completeCommand(name: string) {
    delete commandAttemptRef.current[name];
  }

  async function saveDraft() {
    if (!editable || geometryErrors.length > 0 || busy !== null) {
      return;
    }
    const base = commandTargets.lifecycle;
    if (currentRegionSet !== null && base === null) {
      return;
    }
    const payload = {
      base_region_set_id: base?.id ?? null,
      base_version: base?.version ?? null,
      regions,
    };
    const fingerprint = snapshotFingerprint(regions);
    setBusy("save");
    setCommandError(null);
    setNotice(null);
    try {
      const saved = await saveRegionSet(
        projectId,
        payload,
        commandKey("save", fingerprint),
      );
      completeCommand("save");
      setNotice(`Draft v${saved.version} saved as an immutable snapshot.`);
      load();
    } catch (error) {
      setCommandError(commandMessage(apiError(error)));
    } finally {
      setBusy(null);
    }
  }

  async function submitDraft() {
    const target = commandTargets.lifecycle;
    if (
      target === null ||
      target.effective_lifecycle !== "draft" ||
      target.stale ||
      busy !== null
    ) {
      return;
    }
    setBusy("submit");
    setCommandError(null);
    try {
      const submitted = await submitRegionSet(
        projectId,
        target.id,
        commandKey("submit", target.geometry_fingerprint),
      );
      completeCommand("submit");
      setNotice(`Snapshot v${submitted.version} submitted for human review.`);
      load();
    } catch (error) {
      setCommandError(commandMessage(apiError(error)));
    } finally {
      setBusy(null);
    }
  }

  async function review(verdict: "approved" | "changes_requested") {
    const target = commandTargets.lifecycle;
    if (
      target === null ||
      target.effective_lifecycle !== "submitted" ||
      target.stale ||
      busy !== null
    ) {
      return;
    }
    const reason = reviewReason.trim();
    if (verdict === "changes_requested" && !reason) {
      setCommandError("Explain the requested changes before recording the decision.");
      return;
    }
    const fingerprint = [
      target.geometry_fingerprint,
      verdict,
      reason,
    ].join("\u001f");
    setBusy("review");
    setCommandError(null);
    try {
      await createRegionSetReview(
        projectId,
        target.id,
        { verdict, reason: reason || null },
        commandKey("review", fingerprint),
      );
      completeCommand("review");
      setReviewReason("");
      setNotice(
        verdict === "approved"
          ? "The exact submitted snapshot was approved."
          : "Changes were requested against the exact submitted snapshot.",
      );
      load();
    } catch (error) {
      setCommandError(commandMessage(apiError(error)));
    } finally {
      setBusy(null);
    }
  }

  async function openHistory(regionSetId: string) {
    if (busy !== null) {
      return;
    }
    setBusy("history");
    setCommandError(null);
    setViewedRegionSet(null);
    setRegions([]);
    setEditable(false);
    try {
      const snapshot = await getRegionSet(projectId, regionSetId);
      setViewedRegionSet(snapshot);
      setRegions(persistedRegionsToDrafts(snapshot.regions));
      setSelectedKey(snapshot.regions[0]?.stable_region_key ?? null);
      setEditable(false);
      setNotice(
        snapshot.id === currentRegionSet?.id
          ? `Viewing current v${snapshot.version} · ${snapshot.effective_lifecycle}.`
          : `Viewing historical v${snapshot.version} · ${snapshot.effective_lifecycle} · read-only.`,
      );
    } catch (error) {
      setCommandError(commandMessage(apiError(error)));
    } finally {
      setBusy(null);
    }
  }

  function returnToCurrent() {
    if (currentRegionSet === null || busy !== null) {
      return;
    }
    setViewedRegionSet(currentRegionSet);
    setRegions(persistedRegionsToDrafts(currentRegionSet.regions));
    setSelectedKey(currentRegionSet.regions[0]?.stable_region_key ?? null);
    setSelectedVertex(null);
    setEditable(
      currentRegionSet.effective_lifecycle === "draft" && !currentRegionSet.stale,
    );
    setDrawing([]);
    setUndoStack([]);
    setRedoStack([]);
    setCommandError(null);
    setNotice(`Returned to current v${currentRegionSet.version}.`);
  }

  async function forkHistoricalSnapshot() {
    const target = commandTargets.fork;
    if (
      target === null ||
      busy !== null ||
      workbench?.image_set_status !== "ready"
    ) {
      return;
    }
    const fingerprint = [
      target.source.id,
      target.current.id,
      target.current.version,
    ].join("\u001f");
    setBusy("fork");
    setCommandError(null);
    setNotice(null);
    try {
      const draft = await forkRegionSetDraft(
        projectId,
        target.source.id,
        {
          expected_current_region_set_id: target.current.id,
          expected_current_version: target.current.version,
        },
        commandKey("fork", fingerprint),
      );
      completeCommand("fork");
      setState((currentState) => {
        if (currentState.status !== "loaded") {
          return currentState;
        }
        return {
          status: "loaded",
          workbench: {
            ...currentState.workbench,
            current_region_set: draft,
            history: [
              draft,
              ...currentState.workbench.history.map((item) => ({
                ...item,
                is_current: false,
              })),
            ],
          },
        };
      });
      setViewedRegionSet(draft);
      setRegions(persistedRegionsToDrafts(draft.regions));
      setSelectedKey(draft.regions[0]?.stable_region_key ?? null);
      setSelectedVertex(null);
      setEditable(!draft.stale);
      setDrawing([]);
      setUndoStack([]);
      setRedoStack([]);
      setNotice(
        `Draft v${draft.version} created from historical v${target.source.version}.`,
      );
    } catch (error) {
      setCommandError(commandMessage(apiError(error)));
    } finally {
      setBusy(null);
    }
  }

  function finishDrawing() {
    if (drawing.length < 3) {
      setCommandError("Add at least three points before closing the polygon.");
      return;
    }
    const region = makeRegion(drawing, regions.length);
    commitRegions([...regions, region]);
    setSelectedKey(region.stable_region_key);
    setSelectedVertex(null);
    setDrawing([]);
    setTool("edit");
  }

  function canvasPointerDown(event: ReactPointerEvent<SVGSVGElement>) {
    const svg = event.currentTarget;
    if (
      svgRef.current !== svg ||
      event.isPrimary === false ||
      (event.pointerType === "mouse" && event.button !== 0)
    ) {
      return;
    }
    if (tool === "pan") {
      event.preventDefault();
      setPanStart({
        clientX: event.clientX,
        clientY: event.clientY,
        viewBox,
      });
      svg.setPointerCapture(event.pointerId);
      return;
    }
    if (
      tool === "draw" &&
      editable &&
      !isInteractiveCanvasTarget(event.target, svg)
    ) {
      const point = exactPoint(event, svg);
      if (point !== null) {
        event.preventDefault();
        setDrawing((points) => [...points, point]);
      }
    }
  }

  function canvasPointerMove(event: ReactPointerEvent<SVGSVGElement>) {
    const svg = event.currentTarget;
    if (svgRef.current !== svg || event.isPrimary === false) {
      return;
    }
    if (panStart !== null) {
      const bounds = svg.getBoundingClientRect();
      setViewBox({
        ...panStart.viewBox,
        x:
          panStart.viewBox.x -
          ((event.clientX - panStart.clientX) / bounds.width) *
            panStart.viewBox.width,
        y:
          panStart.viewBox.y -
          ((event.clientY - panStart.clientY) / bounds.height) *
            panStart.viewBox.height,
      });
      return;
    }
    if (draggingVertex !== null && editable) {
      const point = exactPoint(event, svg);
      if (point === null) {
        return;
      }
      event.preventDefault();
      setRegions((current) =>
        current.map((region) =>
          region.stable_region_key === draggingVertex.key
            ? {
                ...region,
                vertices: region.vertices.map((vertex, index) =>
                  index === draggingVertex.index ? point : vertex,
                ),
              }
            : region,
        ),
      );
    }
  }

  function canvasPointerUp(event: ReactPointerEvent<SVGSVGElement>) {
    if (panStart !== null) {
      setPanStart(null);
      svgRef.current?.releasePointerCapture(event.pointerId);
    }
    if (draggingVertex !== null) {
      const dragSnapshot = dragStartSnapshotRef.current;
      if (dragSnapshot !== null) {
        setUndoStack((stack) => [...stack.slice(-49), dragSnapshot]);
        setRedoStack([]);
      }
      dragStartSnapshotRef.current = null;
      setDraggingVertex(null);
      svgRef.current?.releasePointerCapture(event.pointerId);
    }
  }

  function canvasWheel(event: WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    const factor = event.deltaY < 0 ? 0.84 : 1.19;
    const nextWidth = Math.max(120_000, Math.min(1_600_000, viewBox.width * factor));
    const nextHeight = Math.max(
      120_000,
      Math.min(1_600_000, viewBox.height * factor),
    );
    setViewBox({
      x: viewBox.x + (viewBox.width - nextWidth) / 2,
      y: viewBox.y + (viewBox.height - nextHeight) / 2,
      width: nextWidth,
      height: nextHeight,
    });
  }

  function fieldChange(
    field: "kind" | "label" | "notes" | "opacity_ppm",
    event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>,
  ) {
    const value =
      field === "opacity_ppm"
        ? Math.round(Number(event.target.value) * 10_000)
        : event.target.value;
    updateSelected((region) => ({
      ...region,
      [field]: field === "notes" && value === "" ? null : value,
    }));
  }

  function opacityInput(event: FormEvent<HTMLInputElement>) {
    const value = Math.round(Number(event.currentTarget.value) * 10_000);
    updateSelected((region) => ({
      ...region,
      opacity_ppm: value,
    }));
  }

  function moveSelected(offset: -1 | 1) {
    const targetIndex = selectedIndex + offset;
    if (
      !editable ||
      selectedIndex < 0 ||
      targetIndex < 0 ||
      targetIndex >= regions.length
    ) {
      return;
    }
    const next = [...regions];
    [next[selectedIndex], next[targetIndex]] = [
      next[targetIndex]!,
      next[selectedIndex]!,
    ];
    commitRegions(
      next.map((region, index) => ({
        ...region,
        z_index: index,
      })),
    );
  }

  function handlePanelKeyDown(event: ReactKeyboardEvent<HTMLElement>) {
    if (event.key === "Enter" && tool === "draw" && drawing.length >= 3) {
      event.preventDefault();
      finishDrawing();
    }
  }

  if (state.status === "loading") {
    return (
      <section aria-busy="true" className="region-workspace-loading">
        <p className="eyebrow">Human region annotation</p>
        <h1>Loading annotation workspace</h1>
        <p role="status">Reading the current image and immutable RegionSet history…</p>
      </section>
    );
  }

  if (state.status === "error") {
    if (state.error.kind === "not_found") {
      return (
        <FeedbackPanel
          eyebrow="Region workspace not found"
          heading="This project is unavailable"
          headingLevel={1}
          kind="error"
        >
          <p>
            The project may not exist or may belong to another operator. The same safe
            not-found response is used for both cases.
          </p>
        </FeedbackPanel>
      );
    }
    return (
      <FeedbackPanel
        action={{ label: "Retry workspace", onClick: load }}
        eyebrow="Region workspace unavailable"
        heading="The annotation workspace could not be loaded"
        headingLevel={1}
        kind="error"
      >
        <p>{commandMessage(state.error)}</p>
      </FeedbackPanel>
    );
  }

  if (
    workbench === null ||
    workbench.source_content_url === null ||
    workbench.source_image_width === null ||
    workbench.source_image_height === null
  ) {
    return (
      <FeedbackPanel
        eyebrow="Image set required"
        heading="Complete the human-reviewed image set first"
        headingLevel={1}
        kind="error"
      >
        <p>
          Region drawing opens only when the required private image roles have a
          current READY review.
        </p>
      </FeedbackPanel>
    );
  }

  if (currentRegionSet !== null && viewedRegionSet === null) {
    return (
      <section aria-busy="true" className="region-workspace-loading">
        <p className="eyebrow">Human region annotation</p>
        <h1>Loading selected snapshot</h1>
        <p role="status">
          Lifecycle commands remain locked until the displayed snapshot is loaded.
        </p>
      </section>
    );
  }

  const presentedRegionSet = viewedRegionSet;
  const presentedImageWidth =
    presentedRegionSet?.source_image_width ?? workbench.source_image_width;
  const presentedImageHeight =
    presentedRegionSet?.source_image_height ?? workbench.source_image_height;
  const presentedContentUrl =
    presentedRegionSet?.source_content_url ?? workbench.source_content_url;
  const canStartDraftFromCurrent =
    commandTargets.lifecycle !== null &&
    ["approved", "changes_requested"].includes(
      commandTargets.lifecycle.effective_lifecycle,
    );
  const canSubmit =
    commandTargets.lifecycle !== null &&
    commandTargets.lifecycle.effective_lifecycle === "draft" &&
    !commandTargets.lifecycle.stale &&
    commandTargets.lifecycle.region_count > 0;
  const canReview =
    commandTargets.lifecycle !== null &&
    commandTargets.lifecycle.effective_lifecycle === "submitted" &&
    !commandTargets.lifecycle.stale;

  return (
    <section
      className="region-workspace"
      onKeyDown={handlePanelKeyDown}
      aria-labelledby="region-workspace-heading"
    >
      <header className="region-workspace__header">
        <div>
          <p className="eyebrow">Phase 1F · human-governed</p>
          <h1 id="region-workspace-heading" ref={headingRef}>
            Region annotation workspace
          </h1>
          <p>
            Draw and review simple polygons by hand. Coordinates are saved as
            normalized integers, and every save creates a new immutable snapshot.
          </p>
        </div>
        <div className="region-status" aria-label="Displayed RegionSet status">
          <span>
            {presentedRegionSet === null
              ? "unsaved"
              : `v${presentedRegionSet.version} · ${presentedRegionSet.id}`}
          </span>
          <strong>
            {presentedRegionSet?.effective_lifecycle.replaceAll("_", " ") ??
              "new draft"}
          </strong>
        </div>
      </header>

      {commandTargets.isViewingHistoricalSnapshot ? (
        <div className="region-banner region-banner--warning" role="status">
          <strong>Historical snapshot · read-only.</strong> Save, Submit, Approve,
          and Request Changes are unavailable. Create a new draft from this exact
          version or return to the current version.
        </div>
      ) : null}
      {!commandTargets.isViewingHistoricalSnapshot && presentedRegionSet?.stale ? (
        <div className="region-banner region-banner--warning" role="alert">
          <strong>Source image set changed.</strong> This snapshot is read-only and
          cannot be submitted or reviewed. Create a new draft against the current
          READY image set.
        </div>
      ) : null}
      {workbench.image_set_status !== "ready" ? (
        <div className="region-banner region-banner--warning" role="alert">
          The current image set is {workbench.image_set_status}. Region commands are
          locked until a new human READY review is recorded.
        </div>
      ) : null}
      <div className="region-banner region-banner--boundary">
        Human-authored polygons only. This workspace does not generate regions,
        recognize subjects, match inventory, or create paint plans.
      </div>
      {notice !== null ? (
        <div className="region-banner region-banner--success" role="status">
          {notice}
        </div>
      ) : null}
      {commandError !== null ? (
        <div className="region-banner region-banner--error" role="alert">
          {commandError}
        </div>
      ) : null}

      <div className="region-toolbar" aria-label="Annotation tools">
        <div role="group" aria-label="Canvas tool">
          {(["edit", "draw", "pan"] as const).map((item) => (
            <button
              aria-pressed={tool === item}
              className={tool === item ? "is-active" : undefined}
              disabled={item === "draw" && !editable}
              key={item}
              onClick={() => setTool(item)}
              type="button"
            >
              {item === "edit" ? "Edit vertices" : item === "draw" ? "Draw polygon" : "Pan"}
            </button>
          ))}
        </div>
        <div role="group" aria-label="Edit history">
          <button disabled={!editable || undoStack.length === 0} onClick={undo} type="button">
            Undo
          </button>
          <button disabled={!editable || redoStack.length === 0} onClick={redo} type="button">
            Redo
          </button>
          <button onClick={() => setViewBox(defaultViewBox)} type="button">
            Fit image
          </button>
        </div>
        {drawing.length > 0 ? (
          <div role="group" aria-label="Open polygon">
            <span>{drawing.length} points</span>
            <button disabled={drawing.length < 3} onClick={finishDrawing} type="button">
              Close polygon
            </button>
            <button onClick={() => setDrawing([])} type="button">
              Cancel
            </button>
          </div>
        ) : null}
      </div>

      <div className="region-workspace__grid">
        <div className={`region-canvas region-canvas--${tool}`}>
          <div
            className="region-canvas__surface"
            style={{
              aspectRatio: `${presentedImageWidth} / ${presentedImageHeight}`,
            }}
          >
            <svg
              aria-label="Private primary image with region overlay"
              height="100%"
              onPointerDown={canvasPointerDown}
              onPointerMove={canvasPointerMove}
              onPointerUp={canvasPointerUp}
              onWheel={canvasWheel}
              preserveAspectRatio="none"
              ref={svgRef}
              role="img"
              viewBox={`${viewBox.x} ${viewBox.y} ${viewBox.width} ${viewBox.height}`}
              width="100%"
              xmlns="http://www.w3.org/2000/svg"
            >
              <image
                aria-hidden="true"
                height={PPM_MAX}
                href={presentedContentUrl}
                preserveAspectRatio="none"
                width={PPM_MAX}
                x="0"
                y="0"
              />
              <defs>
                {regions.map((region, regionIndex) =>
                  region.kind === "exclude" ? (
                    <pattern
                      height="24000"
                      id={`exclude-pattern-${region.stable_region_key}`}
                      key={region.stable_region_key}
                      patternUnits="userSpaceOnUse"
                      width="24000"
                    >
                      <rect
                        fill={regionColors[regionIndex % regionColors.length]}
                        fillOpacity={region.opacity_ppm / PPM_MAX}
                        height="24000"
                        width="24000"
                      />
                      <path
                        d="M -6000 6000 L 6000 -6000 M 0 24000 L 24000 0 M 18000 30000 L 30000 18000"
                        stroke="#102128"
                        strokeOpacity={region.opacity_ppm / PPM_MAX}
                        strokeWidth="5000"
                      />
                    </pattern>
                  ) : null,
                )}
              </defs>
              {regions.map((region, regionIndex) =>
                hiddenKeys.has(region.stable_region_key) ? null : (
                  <g
                    key={region.stable_region_key}
                    pointerEvents={tool === "draw" ? "none" : "auto"}
                  >
                    <polygon
                      aria-label={`${region.label} region`}
                      data-region-interactive="true"
                      data-region-kind={region.kind}
                      data-selected={region.stable_region_key === selectedKey}
                      fill={
                        region.kind === "exclude"
                          ? `url(#exclude-pattern-${region.stable_region_key})`
                          : regionColors[regionIndex % regionColors.length]
                      }
                      fillOpacity={
                        region.kind === "exclude"
                          ? 1
                          : region.opacity_ppm / PPM_MAX
                      }
                      onPointerDown={(event) => {
                        event.stopPropagation();
                        setSelectedKey(region.stable_region_key);
                        setSelectedVertex(null);
                      }}
                      points={region.vertices
                        .map((vertex) => `${vertex.x_ppm},${vertex.y_ppm}`)
                        .join(" ")}
                      stroke={
                        region.stable_region_key === selectedKey ? "#ffffff" : "#102128"
                      }
                      strokeWidth={Math.max(2500, viewBox.width / 260)}
                    />
                    {tool === "edit" &&
                    editable &&
                    region.stable_region_key === selectedKey
                      ? region.vertices.map((vertex, index) => (
                          <circle
                            aria-label={`${region.label} vertex ${index + 1}`}
                            cx={vertex.x_ppm}
                            cy={vertex.y_ppm}
                            data-region-interactive="true"
                            fill={selectedVertex === index ? "#d2a45f" : "#ffffff"}
                            key={`${region.stable_region_key}:${index}`}
                            onPointerDown={(event) => {
                              event.stopPropagation();
                              setSelectedVertex(index);
                              dragStartSnapshotRef.current =
                                snapshotFingerprint(regions);
                              setDraggingVertex({
                                key: region.stable_region_key,
                                index,
                              });
                              svgRef.current?.setPointerCapture(event.pointerId);
                            }}
                            r={Math.max(7000, viewBox.width / 95)}
                            stroke="#102128"
                            strokeWidth={2500}
                          />
                        ))
                      : null}
                  </g>
                ),
              )}
              {drawing.length > 0 ? (
                <g pointerEvents="none">
                  <polyline
                    fill="none"
                    points={drawing.map((point) => `${point.x_ppm},${point.y_ppm}`).join(" ")}
                    stroke="#ffffff"
                    strokeDasharray="12000 9000"
                    strokeWidth={Math.max(3500, viewBox.width / 220)}
                  />
                  {drawing.map((point, index) => (
                    <circle
                      cx={point.x_ppm}
                      cy={point.y_ppm}
                      fill="#d2a45f"
                      key={`${point.x_ppm}:${point.y_ppm}:${index}`}
                      r={Math.max(7000, viewBox.width / 95)}
                    />
                  ))}
                </g>
              ) : null}
            </svg>
          </div>
          <p className="region-canvas__mobile-note">
            <strong>Small-screen editing is limited.</strong> Use Pan and Fit image to
            inspect the complete canvas; saved Polygon data and history remain
            available. Use a larger screen for precise vertex placement.
          </p>
        </div>

        <aside className="region-inspector" aria-label="Region inspector">
          <div className="region-inspector__heading">
            <div>
              <p className="eyebrow">Snapshot contents</p>
              <h2>{regions.length} regions</h2>
            </div>
            {commandTargets.isViewingHistoricalSnapshot ? (
              <button
                className="button button--primary"
                disabled={busy !== null || workbench.image_set_status !== "ready"}
                onClick={() => void forkHistoricalSnapshot()}
                type="button"
              >
                {busy === "fork"
                  ? "Creating draft…"
                  : "Create new draft from this version"}
              </button>
            ) : canStartDraftFromCurrent ? (
              <button
                className="button button--secondary"
                disabled={busy !== null || workbench.image_set_status !== "ready"}
                onClick={() => {
                  setEditable(true);
                  setNotice("Editing a new draft based on the reviewed snapshot.");
                }}
                type="button"
              >
                Create draft from current
              </button>
            ) : null}
          </div>

          <ol
            aria-label="Regions in back-to-front order"
            className="region-list"
          >
            {regions.map((region, index) => (
              <li
                className={
                  region.stable_region_key === selectedKey ? "is-selected" : undefined
                }
                key={region.stable_region_key}
              >
                <button
                  onClick={() => {
                    setSelectedKey(region.stable_region_key);
                    setSelectedVertex(null);
                  }}
                  type="button"
                >
                  <span
                    aria-hidden="true"
                    style={{ background: regionColors[index % regionColors.length] }}
                  />
                  <strong>{region.label}</strong>
                  <small>
                    {region.kind} · {region.vertices.length} vertices
                  </small>
                </button>
                <button
                  aria-label={`${hiddenKeys.has(region.stable_region_key) ? "Show" : "Hide"} ${region.label}`}
                  onClick={() =>
                    setHiddenKeys((current) => {
                      const next = new Set(current);
                      if (next.has(region.stable_region_key)) {
                        next.delete(region.stable_region_key);
                      } else {
                        next.add(region.stable_region_key);
                      }
                      return next;
                    })
                  }
                  type="button"
                >
                  {hiddenKeys.has(region.stable_region_key) ? "Show" : "Hide"}
                </button>
              </li>
            ))}
          </ol>

          {selected !== null ? (
            <div className="region-fields">
              <label>
                Label
                <input
                  disabled={!editable}
                  maxLength={80}
                  onChange={(event) => fieldChange("label", event)}
                  value={selected.label}
                />
              </label>
              <label>
                Kind
                <select
                  disabled={!editable}
                  onChange={(event) => fieldChange("kind", event)}
                  value={selected.kind}
                >
                  <option value="paint">Paint</option>
                  <option value="exclude">Exclude</option>
                </select>
              </label>
              <label>
                Opacity · {Math.round(selected.opacity_ppm / 10_000)}%
                <input
                  disabled={!editable}
                  max="100"
                  min="10"
                  onInput={opacityInput}
                  step="1"
                  type="range"
                  value={selected.opacity_ppm / 10_000}
                />
              </label>
              <label>
                Notes
                <textarea
                  disabled={!editable}
                  maxLength={1000}
                  onChange={(event) => fieldChange("notes", event)}
                  rows={3}
                  value={selected.notes ?? ""}
                />
              </label>
              <div className="region-fields__actions">
                <button
                  disabled={!editable || selectedIndex <= 0}
                  onClick={() => moveSelected(-1)}
                  type="button"
                >
                  Move backward
                </button>
                <button
                  disabled={!editable || selectedIndex >= regions.length - 1}
                  onClick={() => moveSelected(1)}
                  type="button"
                >
                  Move forward
                </button>
                <button
                  disabled={!editable || selectedVertex === null}
                  onClick={() => {
                    if (selectedVertex === null) {
                      return;
                    }
                    updateSelected((region) => {
                      const current = region.vertices[selectedVertex]!;
                      const next =
                        region.vertices[
                          (selectedVertex + 1) % region.vertices.length
                        ]!;
                      const vertices = [...region.vertices];
                      vertices.splice(selectedVertex + 1, 0, {
                        x_ppm: Math.round((current.x_ppm + next.x_ppm) / 2),
                        y_ppm: Math.round((current.y_ppm + next.y_ppm) / 2),
                      });
                      return { ...region, vertices };
                    });
                  }}
                  type="button"
                >
                  Insert after vertex
                </button>
                <button
                  disabled={
                    !editable ||
                    selectedVertex === null ||
                    selected.vertices.length <= 3
                  }
                  onClick={() => {
                    if (selectedVertex === null) {
                      return;
                    }
                    updateSelected((region) => ({
                      ...region,
                      vertices: region.vertices.filter(
                        (_, index) => index !== selectedVertex,
                      ),
                    }));
                    setSelectedVertex(null);
                  }}
                  type="button"
                >
                  Delete vertex
                </button>
                <button
                  disabled={!editable}
                  onClick={() => {
                    const next = regions
                      .filter((region) => region.stable_region_key !== selectedKey)
                      .map((region, index) => ({ ...region, z_index: index }));
                    commitRegions(next);
                    setSelectedKey(next[0]?.stable_region_key ?? null);
                    setSelectedVertex(null);
                  }}
                  type="button"
                >
                  Delete region
                </button>
              </div>
            </div>
          ) : (
            <p className="region-inspector__empty">
              Choose a region or use Draw polygon to add one.
            </p>
          )}

          {geometryErrors.length > 0 ? (
            <div className="region-validation" role="alert">
              <strong>Fix before saving</strong>
              <ul>
                {geometryErrors.slice(0, 5).map((error) => (
                  <li key={error}>{error}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {!commandTargets.isViewingHistoricalSnapshot ? (
            <div className="region-command-bar">
              <button
                className="button button--secondary"
                disabled={!editable || geometryErrors.length > 0 || busy !== null}
                onClick={() => void saveDraft()}
                type="button"
              >
                {busy === "save" ? "Saving…" : "Save new draft snapshot"}
              </button>
              <button
                className="button button--primary"
                disabled={!canSubmit || busy !== null}
                onClick={() => void submitDraft()}
                type="button"
              >
                {busy === "submit" ? "Submitting…" : "Submit saved draft"}
              </button>
            </div>
          ) : null}

          {canReview ? (
            <div className="region-review">
              <p className="eyebrow">Exact-snapshot review</p>
              <h3>Record a human decision</h3>
              <label>
                Reason for requested changes
                <textarea
                  disabled={busy !== null}
                  maxLength={1000}
                  onChange={(event) => setReviewReason(event.target.value)}
                  rows={3}
                  value={reviewReason}
                />
              </label>
              <div>
                <button
                  className="button button--secondary"
                  disabled={busy !== null}
                  onClick={() => void review("changes_requested")}
                  type="button"
                >
                  Request changes
                </button>
                <button
                  className="button button--primary"
                  disabled={busy !== null}
                  onClick={() => void review("approved")}
                  type="button"
                >
                  Approve exact snapshot
                </button>
              </div>
            </div>
          ) : null}
        </aside>
      </div>

      <section className="region-history" aria-labelledby="region-history-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Append-only record</p>
            <h2 id="region-history-heading">RegionSet history</h2>
          </div>
          <div>
            {commandTargets.isViewingHistoricalSnapshot ? (
              <button
                className="button button--secondary"
                disabled={busy !== null}
                onClick={returnToCurrent}
                type="button"
              >
                Return to current version
              </button>
            ) : null}
            <button className="button button--secondary" onClick={load} type="button">
              Refresh workbench
            </button>
          </div>
        </div>
        {workbench.history.length === 0 ? (
          <p>No saved snapshots yet.</p>
        ) : (
          <ol>
            {workbench.history.map((item) => (
              <li key={item.id}>
                <button
                  disabled={busy !== null}
                  onClick={() => void openHistory(item.id)}
                  type="button"
                >
                  <strong>v{item.version}</strong>
                  <span>{item.effective_lifecycle.replaceAll("_", " ")}</span>
                  <span>
                    {item.region_count} regions · {item.total_vertex_count} vertices
                  </span>
                  <time dateTime={item.created_at}>
                    {formatProjectTimestamp(item.created_at)}
                  </time>
                  {item.stale ? <em>stale source</em> : null}
                  {item.latest_review !== null ? (
                    <span className="region-history__review">
                      Review by{" "}
                      {item.latest_review.actor_display_name_snapshot} ·{" "}
                      {formatProjectTimestamp(item.latest_review.created_at)}
                      {item.latest_review.reason === null ? null : (
                        <> · {item.latest_review.reason}</>
                      )}
                    </span>
                  ) : null}
                </button>
              </li>
            ))}
          </ol>
        )}
      </section>
    </section>
  );
}
