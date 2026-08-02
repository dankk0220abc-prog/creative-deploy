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
import { useAppTranslation } from "../i18n";
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
  canEdit?: boolean;
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

interface LocalizedMessage {
  key: string;
  values?: Record<string, string | number>;
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

function commandMessageKey(error: RegionSetApiError): string {
  if (error.kind === "network") {
    return "region.error.network";
  }
  if (error.kind === "conflict") {
    return "region.error.conflict";
  }
  if (error.kind === "validation") {
    return "region.error.validation";
  }
  if (error.kind === "not_found") {
    return "region.error.notFound";
  }
  return "region.error.unexpected";
}

function snapshotFingerprint(regions: RegionDraftInput[]): string {
  return JSON.stringify(regions);
}

function makeRegion(vertices: Point[], zIndex: number, label: string): RegionDraftInput {
  return {
    stable_region_key: crypto.randomUUID(),
    kind: "paint",
    label,
    z_index: zIndex,
    opacity_ppm: 500_000,
    notes: null,
    vertices,
  };
}

function geometryMessage(error: string): LocalizedMessage {
  const exact: Record<string, string> = {
    "A snapshot can contain at most 128 regions.": "region.validation.maxRegions",
    "A snapshot can contain at most 8,192 vertices.": "region.validation.maxVertices",
    "Every region needs a label of 80 characters or fewer.": "region.validation.label",
  };
  if (exact[error] !== undefined) return { key: exact[error] };
  const match = /^Region “(.+)” (has a duplicate stable key|has a duplicate layer position|needs between 3 and 256 vertices|has an out-of-bounds vertex|has a zero-length edge|crosses itself|is too small)\.$/.exec(error);
  if (match === null) return { key: "region.error.validation" };
  const keys: Record<string, string> = {
    "has a duplicate stable key": "region.validation.duplicateKey",
    "has a duplicate layer position": "region.validation.duplicateLayer",
    "needs between 3 and 256 vertices": "region.validation.vertices",
    "has an out-of-bounds vertex": "region.validation.bounds",
    "has a zero-length edge": "region.validation.edge",
    "crosses itself": "region.validation.crosses",
    "is too small": "region.validation.small",
  };
  return { key: keys[match[2]!] ?? "region.error.validation", values: { label: match[1]! } };
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
  canEdit,
  onViewStateChange,
  projectId,
}: RegionAnnotationWorkspaceProps) {
  const { t } = useAppTranslation();
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
  const [commandError, setCommandError] = useState<LocalizedMessage | null>(null);
  const [notice, setNotice] = useState<LocalizedMessage | null>(null);
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
        const canEditLoadedProject =
          canEdit ?? workbench.access_role === "owner";
        setState({ status: "loaded", workbench });
        setViewedRegionSet(current);
        setRegions(
          current === null ? [] : persistedRegionsToDrafts(current.regions),
        );
        setSelectedKey(current?.regions[0]?.stable_region_key ?? null);
        setSelectedVertex(null);
        setEditable(
          canEditLoadedProject &&
            (current === null
              ? workbench.can_create_draft
              : current.effective_lifecycle === "draft" && !current.stale),
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
  }, [canEdit, projectId, reloadToken]);

  const workbench = state.status === "loaded" ? state.workbench : null;
  const canEditProject =
    canEdit ?? workbench?.access_role !== "reviewer";
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
      setNotice({ key: "region.notice.saved", values: { version: saved.version } });
      load();
    } catch (error) {
      setCommandError({ key: commandMessageKey(apiError(error)) });
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
      setNotice({ key: "region.notice.submitted", values: { version: submitted.version } });
      load();
    } catch (error) {
      setCommandError({ key: commandMessageKey(apiError(error)) });
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
      setCommandError({ key: "region.review.reasonRequired" });
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
      setNotice({
        key: verdict === "approved" ? "region.notice.approved" : "region.notice.changes",
      });
      load();
    } catch (error) {
      setCommandError({ key: commandMessageKey(apiError(error)) });
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
      setNotice({
        key: snapshot.id === currentRegionSet?.id
          ? "region.notice.viewCurrent"
          : "region.notice.viewHistorical",
        values: {
          version: snapshot.version,
          lifecycle: t(`region.lifecycle.${snapshot.effective_lifecycle}`),
        },
      });
    } catch (error) {
      setCommandError({ key: commandMessageKey(apiError(error)) });
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
      canEditProject &&
        currentRegionSet.effective_lifecycle === "draft" &&
        !currentRegionSet.stale,
    );
    setDrawing([]);
    setUndoStack([]);
    setRedoStack([]);
    setCommandError(null);
    setNotice({ key: "region.notice.returned", values: { version: currentRegionSet.version } });
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
      setEditable(canEditProject && !draft.stale);
      setDrawing([]);
      setUndoStack([]);
      setRedoStack([]);
      setNotice({
        key: "region.notice.forked",
        values: { version: draft.version, sourceVersion: target.source.version },
      });
    } catch (error) {
      setCommandError({ key: commandMessageKey(apiError(error)) });
    } finally {
      setBusy(null);
    }
  }

  function finishDrawing() {
    if (drawing.length < 3) {
      setCommandError({ key: "region.error.points" });
      return;
    }
    const region = makeRegion(
      drawing,
      regions.length,
      t("region.defaultLabel", { number: regions.length + 1 }),
    );
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
        <p className="context-label">{t("region.loadingEyebrow")}</p>
        <h1>{t("region.loadingHeading")}</h1>
        <p role="status">{t("region.loadingCopy")}</p>
      </section>
    );
  }

  if (state.status === "error") {
    if (state.error.kind === "not_found") {
      return (
        <FeedbackPanel
          eyebrow={t("region.notFound")}
          heading={t("region.projectUnavailable")}
          headingLevel={1}
          kind="error"
        >
          <p>{t("region.notFoundCopy")}</p>
        </FeedbackPanel>
      );
    }
    return (
      <FeedbackPanel
        action={{ label: t("region.retry"), onClick: load }}
        eyebrow={t("region.unavailable")}
        heading={t("region.unavailableHeading")}
        headingLevel={1}
        kind="error"
      >
        <p>{t(commandMessageKey(state.error))}</p>
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
        eyebrow={t("region.imageRequired")}
        heading={t("region.imageRequiredHeading")}
        headingLevel={1}
        kind="error"
      >
        <p>{t("region.imageRequiredCopy")}</p>
      </FeedbackPanel>
    );
  }

  if (currentRegionSet !== null && viewedRegionSet === null) {
    return (
      <section aria-busy="true" className="region-workspace-loading">
        <p className="context-label">{t("region.loadingEyebrow")}</p>
        <h1>{t("region.loadingSnapshot")}</h1>
        <p role="status">{t("region.loadingSnapshotCopy")}</p>
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
    canEditProject &&
    commandTargets.lifecycle !== null &&
    ["approved", "changes_requested"].includes(
      commandTargets.lifecycle.effective_lifecycle,
    );
  const canSubmit =
    canEditProject &&
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
          <p className="context-label">{t("region.eyebrow")}</p>
          <h1 id="region-workspace-heading" ref={headingRef}>
            {t("region.heading")}
          </h1>
          <p>{t("region.lede")}</p>
        </div>
        <div className="region-status" aria-label={t("region.displayedStatus")}>
          <span>
            {presentedRegionSet === null
              ? t("region.unsaved")
              : `v${presentedRegionSet.version} · ${presentedRegionSet.id}`}
          </span>
          <strong>
            {presentedRegionSet === null
              ? t("region.newDraft")
              : t(`region.lifecycle.${presentedRegionSet.effective_lifecycle}`)}
          </strong>
        </div>
      </header>

      {commandTargets.isViewingHistoricalSnapshot ? (
        <div className="region-banner region-banner--warning" role="status">
          <strong>{t("region.historicalStrong")}</strong> {t("region.historicalCopy")}
        </div>
      ) : null}
      {!commandTargets.isViewingHistoricalSnapshot && presentedRegionSet?.stale ? (
        <div className="region-banner region-banner--warning" role="alert">
          <strong>{t("region.staleStrong")}</strong> {t("region.staleCopy")}
        </div>
      ) : null}
      {workbench.image_set_status !== "ready" ? (
        <div className="region-banner region-banner--warning" role="alert">
          {t("region.imageLocked", {
            status: t(`region.imageStatus.${workbench.image_set_status}`),
          })}
        </div>
      ) : null}
      {!canEditProject ? (
        <div className="region-banner region-banner--boundary" role="note">
          {t("region.reviewerBoundary")}
        </div>
      ) : null}
      <div className="region-banner region-banner--boundary">
        {t("region.boundary")}
      </div>
      {notice !== null ? (
        <div className="region-banner region-banner--success" role="status">
          {t(notice.key, notice.values)}
        </div>
      ) : null}
      {commandError !== null ? (
        <div className="region-banner region-banner--error" role="alert">
          {t(commandError.key, commandError.values)}
        </div>
      ) : null}

      <div className="region-toolbar" aria-label={t("region.toolsLabel")}>
        <div role="group" aria-label={t("region.canvasTool")}>
          {(["edit", "draw", "pan"] as const).map((item) => (
            <button
              aria-pressed={tool === item}
              className={tool === item ? "is-active" : undefined}
              disabled={item === "draw" && !editable}
              key={item}
              onClick={() => setTool(item)}
              type="button"
            >
              {t(`region.tool.${item}`)}
            </button>
          ))}
        </div>
        <div role="group" aria-label={t("region.editHistory")}>
          <button disabled={!editable || undoStack.length === 0} onClick={undo} type="button">
            {t("region.undo")}
          </button>
          <button disabled={!editable || redoStack.length === 0} onClick={redo} type="button">
            {t("region.redo")}
          </button>
          <button onClick={() => setViewBox(defaultViewBox)} type="button">
            {t("region.fit")}
          </button>
        </div>
        {drawing.length > 0 ? (
          <div role="group" aria-label={t("region.openPolygon")}>
            <span>{t("region.points", { count: drawing.length })}</span>
            <button disabled={drawing.length < 3} onClick={finishDrawing} type="button">
              {t("region.closePolygon")}
            </button>
            <button onClick={() => setDrawing([])} type="button">
              {t("common.cancel")}
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
              aria-label={t("region.canvasLabel")}
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
                      aria-label={t("region.regionAria", { label: region.label })}
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
                            aria-label={t("region.vertexAria", { label: region.label, number: index + 1 })}
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
            <strong>{t("region.mobileStrong")}</strong> {t("region.mobileCopy")}
          </p>
        </div>

        <aside className="region-inspector" aria-label={t("region.inspector")}>
          <div className="region-inspector__heading">
            <div>
              <p className="context-label">{t("region.snapshotContents")}</p>
              <h2>{t("region.count", { count: regions.length })}</h2>
            </div>
            {canEditProject && commandTargets.isViewingHistoricalSnapshot ? (
              <button
                className="button button--primary"
                disabled={busy !== null || workbench.image_set_status !== "ready"}
                onClick={() => void forkHistoricalSnapshot()}
                type="button"
              >
                {busy === "fork"
                  ? t("region.creatingDraft")
                  : t("region.createFromVersion")}
              </button>
            ) : canStartDraftFromCurrent ? (
              <button
                className="button button--secondary"
                disabled={busy !== null || workbench.image_set_status !== "ready"}
                onClick={() => {
                  setEditable(true);
                  setNotice({ key: "region.notice.editing" });
                }}
                type="button"
              >
                {t("region.createFromCurrent")}
              </button>
            ) : null}
          </div>

          <ol
            aria-label={t("region.orderLabel")}
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
                    {t("region.summary", {
                      kind: t(`region.kind.${region.kind}`),
                      count: region.vertices.length,
                    })}
                  </small>
                </button>
                <button
                  aria-label={t("region.visibility", {
                    action: hiddenKeys.has(region.stable_region_key) ? t("common.show") : t("common.hide"),
                    label: region.label,
                  })}
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
                  {hiddenKeys.has(region.stable_region_key) ? t("common.show") : t("common.hide")}
                </button>
              </li>
            ))}
          </ol>

          {selected !== null ? (
            <div className="region-fields">
              <label>
                {t("region.field.label")}
                <input
                  disabled={!editable}
                  maxLength={80}
                  onChange={(event) => fieldChange("label", event)}
                  value={selected.label}
                />
              </label>
              <label>
                {t("region.field.kind")}
                <select
                  disabled={!editable}
                  onChange={(event) => fieldChange("kind", event)}
                  value={selected.kind}
                >
                  <option value="paint">{t("region.kind.paint")}</option>
                  <option value="exclude">{t("region.kind.exclude")}</option>
                </select>
              </label>
              <label>
                {t("region.field.opacity", { value: Math.round(selected.opacity_ppm / 10_000) })}
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
                {t("region.field.notes")}
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
                  {t("region.moveBackward")}
                </button>
                <button
                  disabled={!editable || selectedIndex >= regions.length - 1}
                  onClick={() => moveSelected(1)}
                  type="button"
                >
                  {t("region.moveForward")}
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
                  {t("region.insertVertex")}
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
                  {t("region.deleteVertex")}
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
                  {t("region.deleteRegion")}
                </button>
              </div>
            </div>
          ) : (
            <p className="region-inspector__empty">
              {t("region.emptyInspector")}
            </p>
          )}

          {geometryErrors.length > 0 ? (
            <div className="region-validation" role="alert">
              <strong>{t("region.fix")}</strong>
              <ul>
                {geometryErrors.slice(0, 5).map((error) => {
                  const message = geometryMessage(error);
                  return <li key={error}>{t(message.key, message.values)}</li>;
                })}
              </ul>
            </div>
          ) : null}

          {canEditProject && !commandTargets.isViewingHistoricalSnapshot ? (
            <div className="region-command-bar">
              <button
                className="button button--secondary"
                disabled={!editable || geometryErrors.length > 0 || busy !== null}
                onClick={() => void saveDraft()}
                type="button"
              >
                {busy === "save" ? t("region.saving") : t("region.save")}
              </button>
              <button
                className="button button--primary"
                disabled={!canSubmit || busy !== null}
                onClick={() => void submitDraft()}
                type="button"
              >
                {busy === "submit" ? t("region.submitting") : t("region.submit")}
              </button>
            </div>
          ) : null}

          {canReview ? (
            <div className="region-review">
              <p className="context-label">{t("region.reviewEyebrow")}</p>
              <h3>{t("region.reviewHeading")}</h3>
              <label>
                {t("region.reviewReason")}
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
                  aria-busy={busy === "review"}
                  className="button button--secondary"
                  disabled={busy !== null}
                  onClick={() => void review("changes_requested")}
                  type="button"
                >
                  {busy === "review" ? t("region.savingReview") : t("region.requestChanges")}
                </button>
                <button
                  aria-busy={busy === "review"}
                  className="button button--primary"
                  disabled={busy !== null}
                  onClick={() => void review("approved")}
                  type="button"
                >
                  {busy === "review" ? t("region.savingReview") : t("region.approve")}
                </button>
              </div>
            </div>
          ) : null}
        </aside>
      </div>

      <section className="region-history" aria-labelledby="region-history-heading">
        <div className="section-heading">
          <div>
            <p className="context-label">{t("region.historyEyebrow")}</p>
            <h2 id="region-history-heading">{t("region.historyHeading")}</h2>
          </div>
          <div>
            {commandTargets.isViewingHistoricalSnapshot ? (
              <button
                className="button button--secondary"
                disabled={busy !== null}
                onClick={returnToCurrent}
                type="button"
              >
                {t("region.returnCurrent")}
              </button>
            ) : null}
            <button className="button button--secondary" onClick={load} type="button">
              {t("region.refresh")}
            </button>
          </div>
        </div>
        {workbench.history.length === 0 ? (
          <p>{t("region.historyEmpty")}</p>
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
                  <span>{t(`region.lifecycle.${item.effective_lifecycle}`)}</span>
                  <span>
                    {t("region.historyCounts", {
                      regions: item.region_count,
                      vertices: item.total_vertex_count,
                    })}
                  </span>
                  <time dateTime={item.created_at}>
                    {formatProjectTimestamp(item.created_at)}
                  </time>
                  {item.stale ? <em>{t("region.staleSource")}</em> : null}
                  {item.latest_review !== null ? (
                    <span className="region-history__review">
                      {t("region.reviewBy", {
                        name: item.latest_review.actor_display_name_snapshot,
                        date: formatProjectTimestamp(item.latest_review.created_at),
                      })}
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
