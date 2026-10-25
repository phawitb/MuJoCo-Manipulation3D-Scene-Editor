import { useCallback, useEffect, useRef, useState, useMemo } from "react";
import { readCameras } from "./math";
import { readResetJoints } from "./robotPreferences";
import {
  mergePacket,
  visiblePacket,
  persistedJoints,
  type PacketCache,
} from "./packets";
import type { Asset, MeshData, Scene, Snapshot, StatePacket } from "./types";

export function useSimulation() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [status, setStatus] = useState<
    "connecting" | "connected" | "offline" | "recovery-error"
  >("connecting");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [assets, setAssets] = useState<Asset[]>([]);
  const [meshes, setMeshes] = useState<MeshData>({});
  const [state, setState] = useState<StatePacket | null>(null);
  const live = useRef<StatePacket | null>(null);
  const snapshotRef = useRef<Snapshot | null>(null);
  const socket = useRef<WebSocket | null>(null);
  const recovery = useRef<Scene | null>(null);
  const pending = useRef<{
    id: string;
    resolve: (s: StatePacket) => void;
    reject: (e: Error) => void;
    timer: ReturnType<typeof setTimeout>;
  } | null>(null);
  const counter = useRef(0);
  const sessionId = useRef<string | null>(
    new URLSearchParams(location.search).get("session"),
  );
  const serverRevision = useRef<number | undefined>(undefined);
  const recoveryBlocked = useRef(false);
  const busyRef = useRef(false);
  const packets = useRef<PacketCache>({
    snapshot: null,
    latest: null,
    revision: undefined,
  });
  const updatePacket = (packet: StatePacket) => {
    packets.current = mergePacket(packets.current, packet);
    serverRevision.current = Math.max(
      serverRevision.current ?? 0,
      packets.current.revision ?? 0,
    );
    const visible = visiblePacket(packets.current);
    live.current = visible;
    setState(visible);
    if (
      packets.current.snapshot &&
      packets.current.snapshot !== snapshotRef.current
    ) {
      snapshotRef.current = packets.current.snapshot;
      setSnapshot(packets.current.snapshot);
    }
    const scene = snapshotRef.current?.scene;
    if (scene) {
      const saved = { ...scene, objects: scene.objects.map((o) => ({ ...o })) };
      for (const obj of saved.objects) {
        const pose = visible?.objects.find((x) => x.id === obj.id);
        if (pose) {
          obj.position = pose.position;
          obj.quaternion = pose.quaternion;
        }
      }
      if (visible?.joints)
        saved.robot = {
          ...scene.robot,
          joints: persistedJoints(
            visible.joints,
            snapshotRef.current!.jointInfo,
          ),
        };
      recovery.current = saved;
    }
  };
  const command = useCallback(
    (type: string, extra: Record<string, unknown> = {}) =>
      new Promise<StatePacket>((resolve, reject) => {
        if (recoveryBlocked.current && type !== "load" && type !== "reset")
          return reject(
            new Error(
              "Restore failed. Save your retained scene, then open a scene or reset to continue.",
            ),
          );
        if (socket.current?.readyState !== WebSocket.OPEN)
          return reject(new Error("Simulation server is disconnected"));
        if (busyRef.current)
          return reject(new Error("Wait for the current update to finish"));
        const id = `${crypto.randomUUID()}-${++counter.current}`;
        busyRef.current = true;
        setBusy(true);
        setError("");
        const timer = setTimeout(
          () => {
            pending.current = null;
            busyRef.current = false;
            setBusy(false);
            socket.current?.close();
            reject(
              new Error(
                "Server update timed out; reconnecting with your last acknowledged scene",
              ),
            );
          },
          type === "real_run" ? 60000 : 15000,
        );
        pending.current = { id, resolve, reject, timer };
        socket.current.send(
          JSON.stringify({
            type,
            requestId: id,
            revision: serverRevision.current,
            ...extra,
          }),
        );
      }),
    [],
  );
  const waitForPending = useCallback(() => {
    const current = pending.current;
    if (!current) return Promise.resolve();
    return new Promise<void>((resolve, reject) => {
      const accepted = current.resolve;
      const rejected = current.reject;
      current.resolve = (packet) => {
        accepted(packet);
        resolve();
      };
      current.reject = (error) => {
        rejected(error);
        reject(error);
      };
    });
  }, []);
  useEffect(() => {
    let cancelled = false,
      reconnect: ReturnType<typeof setTimeout>,
      assetRetry: ReturnType<typeof setTimeout>;
    const abort = new AbortController();
    const loadAssets = () =>
      Promise.all([
        fetch("/api/assets", { signal: abort.signal }).then((r) => {
          if (!r.ok) throw Error("Asset library unavailable");
          return r.json();
        }),
        fetch("/api/meshes", { signal: abort.signal }).then((r) => {
          if (!r.ok) throw Error("Robot meshes unavailable");
          return r.json();
        }),
      ])
        .then(([a, m]) => {
          if (!cancelled) {
            setAssets(a);
            setMeshes(m);
            setError((previous) =>
              previous.includes("unavailable") ? "" : previous,
            );
          }
        })
        .catch((e) => {
          if (!cancelled) {
            setError(String(e));
            assetRetry = setTimeout(loadAssets, 1500);
          }
        });
    void loadAssets();
    const connect = () => {
      const requestedSession = sessionId.current;
      const ws = new WebSocket(
        `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws${requestedSession ? `?session=${encodeURIComponent(requestedSession)}` : ""}`,
      );
      socket.current = ws;
      let first = true,
        explicitlyClosed = false;
      ws.onmessage = (event) => {
        if (cancelled) return;
        const p = JSON.parse(event.data);
        if (p.type === "closed") {
          explicitlyClosed = true;
          sessionId.current = null;
          ws.close();
          return;
        }
        if (p.type === "error") {
          if (p.revision !== undefined)
            serverRevision.current = Math.max(
              serverRevision.current ?? 0,
              p.revision,
            );
          setError(p.message);
          if (p.code === "session_missing") sessionId.current = null;
          if (pending.current && pending.current.id === p.requestId) {
            clearTimeout(pending.current.timer);
            pending.current.reject(new Error(p.message));
            pending.current = null;
            busyRef.current = false;
            setBusy(false);
          }
          return;
        }
        if (first) {
          first = false;
          sessionId.current = p.sessionId;
          const url = new URL(window.location.href);
          url.searchParams.set("session", p.sessionId);
          window.history.replaceState(window.history.state, "", url);

          // A newly created session starts its own revision counter. Initialize
          // before restoring retained work or local camera preferences.
          serverRevision.current = p.revision;
          if (recovery.current && !requestedSession) {
            const restore = recovery.current;
            setStatus("connecting");
            recoveryBlocked.current = true;
            command("load", { scene: restore }).catch((e) => {
              setStatus("recovery-error");
              setError(
                `Could not restore scene: ${e.message}. Your scene is retained. Save it, then open a scene or reset to continue.`,
              );
            });
            return;
          }
        }
        if (
          !requestedSession &&
          !snapshotRef.current &&
          p.type === "snapshot" &&
          !p.requestId
        ) {
          const cameras = readCameras();
          const resetJoints = readResetJoints(p.jointInfo);
          command("load", {
            scene: {
              ...p.scene,
              robot: resetJoints
                ? {
                    ...p.scene.robot,
                    joints: resetJoints,
                    reset_joints: resetJoints,
                  }
                : p.scene.robot,
              cameras: {
                main: cameras.main,
                top: cameras.top,
                front: cameras.front,
                back: cameras.back,
              },
            },
          }).catch((e) => {
            updatePacket(p);
            setStatus("connected");
            setError(
              `Workspace preferences could not be restored: ${e.message}`,
            );
          });
          return;
        }
        if (p.type === "snapshot") {
          recoveryBlocked.current = false;
          setStatus("connected");
        }
        updatePacket(p);
        if (p.warning) setError(p.warning);
        if (pending.current && pending.current.id === p.requestId) {
          clearTimeout(pending.current.timer);
          pending.current.resolve(p);
          pending.current = null;
          busyRef.current = false;
          setBusy(false);
        }
      };
      ws.onclose = () => {
        if (cancelled) return;
        setStatus("offline");
        if (live.current) {
          live.current = { ...live.current, running: false };
          setState(live.current);
        }
        if (pending.current) {
          clearTimeout(pending.current.timer);
          pending.current.reject(
            new Error("Connection lost; last acknowledged scene retained"),
          );
          pending.current = null;
        }
        busyRef.current = false;
        setBusy(false);
        if (explicitlyClosed) {
          setError(
            "This session was closed by an external controller. Save your retained scene, then reload to start a new session.",
          );
          return;
        }
        reconnect = setTimeout(connect, 1500);
      };
      ws.onerror = () => ws.close();
    };
    connect();
    return () => {
      cancelled = true;
      clearTimeout(reconnect);
      clearTimeout(assetRetry);
      abort.abort();
      socket.current?.close();
      if (pending.current) {
        clearTimeout(pending.current.timer);
        pending.current.reject(new Error("Editor closed"));
        pending.current = null;
      }
      busyRef.current = false;
    };
  }, [command]);
  const currentScene = useCallback(() => {
    if (!snapshotRef.current) throw Error("Scene is still loading");
    const result = structuredClone(snapshotRef.current.scene);
    if (live.current?.joints)
      result.robot.joints = persistedJoints(
        live.current.joints,
        snapshotRef.current.jointInfo,
      );
    for (const obj of result.objects) {
      const p = live.current?.objects.find((x) => x.id === obj.id);
      if (p) {
        obj.position = [...p.position];
        obj.quaternion = [...p.quaternion];
      }
    }
    return result;
  }, []);
  const combinedMeshes = useMemo(
    () => ({ ...meshes, ...snapshot?.meshes }),
    [meshes, snapshot?.meshes],
  );
  return {
    snapshot,
    state,
    live,
    status,
    busy,
    error,
    setError,
    assets,
    meshes: combinedMeshes,
    command,
    waitForPending,
    currentScene,
  };
}
