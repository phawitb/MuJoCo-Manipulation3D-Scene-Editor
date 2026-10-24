import type { Snapshot, StatePacket } from "./types";

export interface PacketCache {
  snapshot: Snapshot | null;
  latest: StatePacket | null;
  revision: number | undefined;
}

export function mergePacket(
  cache: PacketCache,
  packet: StatePacket,
): PacketCache {
  if (cache.latest?.sessionId !== packet.sessionId)
    cache = { snapshot: null, latest: null, revision: undefined };
  // Structure can arrive after newer poses; track its freshness independently.
  const snapshot =
    packet.type === "snapshot" &&
    (!cache.snapshot || packet.sequence >= cache.snapshot.sequence)
      ? (packet as Snapshot)
      : cache.snapshot;
  const latest =
    !cache.latest || packet.sequence >= cache.latest.sequence
      ? packet
      : cache.latest;
  return {
    snapshot,
    latest,
    revision: Math.max(cache.revision ?? 0, packet.revision),
  };
}

// Never combine geometry and poses from different compiled revisions.
export function visiblePacket(cache: PacketCache): StatePacket | null {
  return cache.latest?.revision === cache.snapshot?.revision
    ? cache.latest
    : cache.snapshot;
}
