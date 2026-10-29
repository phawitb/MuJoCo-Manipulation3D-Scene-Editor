import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  Camera,
  Pause,
  Play,
  SkipBack,
  SkipForward,
} from "lucide-react";

interface VideoSource {
  url: string;
  start: number;
  end: number;
}
interface Episode {
  index: number;
  frames: number;
  seed: number;
  outcome: string;
  success: boolean;
  videos: Record<string, VideoSource>;
}
interface Index {
  name: string;
  scene_name: string;
  task: string;
  fps: number;
  cameras: string[];
  joint_names: string[];
  episodes: Episode[];
}
interface Signals {
  episode: number;
  time: number[];
  state: number[][];
  action: number[][];
  velocity: number[][];
  effort: number[][];
  tcp: number[][];
}
type Signal = "state" | "action" | "velocity" | "effort";
const colors = [
  "#a9dbb8",
  "#f3bd77",
  "#89b5ee",
  "#da9ad8",
  "#78d7cf",
  "#f18e8e",
];
const title = (name: string) => name.replaceAll("_", " ");
async function getJSON(response: Response) {
  const data = await response.json();
  if (!response.ok)
    throw Error(
      typeof data.detail === "string" ? data.detail : "Could not load dataset",
    );
  return data;
}

function JointChart({
  values,
  names,
  frame,
  fps,
  units,
  seek,
}: {
  values: number[][];
  names: string[];
  frame: number;
  fps: number;
  units: string;
  seek: (frame: number) => void;
}) {
  const [visible, setVisible] = useState(names.map(() => true));
  const geometry = useMemo(() => {
    let min = Infinity,
      max = -Infinity;
    for (const row of values)
      row.forEach((value, joint) => {
        if (visible[joint]) {
          min = Math.min(min, value);
          max = Math.max(max, value);
        }
      });
    if (!Number.isFinite(min)) {
      min = -1;
      max = 1;
    }
    const padding = Math.max((max - min) * 0.08, 0.05);
    min -= padding;
    max += padding;
    const x = (i: number) => 58 + (i / Math.max(1, values.length - 1)) * 820;
    const y = (v: number) => 208 - ((v - min) / (max - min)) * 180;
    return {
      min,
      max,
      x,
      y,
      paths: names.map((_, joint) =>
        visible[joint]
          ? values
              .map(
                (row, i) =>
                  `${i ? "L" : "M"}${x(i).toFixed(2)},${y(row[joint]).toFixed(2)}`,
              )
              .join(" ")
          : "",
      ),
    };
  }, [values, names, visible]);
  return (
    <div className="dataset-chart">
      <div className="dataset-legend">
        {names.map((name, i) => (
          <button
            key={name}
            aria-pressed={visible[i]}
            onClick={() =>
              setVisible((old) => old.map((v, j) => (j === i ? !v : v)))
            }
          >
            <i style={{ background: colors[i] }} />
            {title(name)}
          </button>
        ))}
      </div>
      <svg
        viewBox="0 0 900 248"
        role="img"
        aria-label="Joint trajectories"
        onClick={(event) => {
          const bounds = event.currentTarget.getBoundingClientRect();
          seek(
            Math.round(
              Math.min(
                1,
                Math.max(
                  0,
                  (((event.clientX - bounds.left) / bounds.width) * 900 - 58) /
                    820,
                ),
              ) *
                (values.length - 1),
            ),
          );
        }}
      >
        <title>
          Click to seek. Use the frame timeline for keyboard navigation.
        </title>
        {[0, 1, 2, 3, 4].map((i) => {
          const value = geometry.min + ((geometry.max - geometry.min) * i) / 4;
          const y = geometry.y(value);
          return (
            <g key={i}>
              <line x1="58" x2="878" y1={y} y2={y} stroke="#344543" />
              <text x="49" y={y + 4} textAnchor="end">
                {value.toFixed(2)}
              </text>
            </g>
          );
        })}
        {geometry.paths.map(
          (d, i) =>
            d && (
              <path
                key={names[i]}
                d={d}
                fill="none"
                stroke={colors[i]}
                strokeWidth="1.8"
              />
            ),
        )}
        <line
          data-testid="trajectory-cursor"
          data-frame={frame}
          x1={geometry.x(frame)}
          x2={geometry.x(frame)}
          y1="20"
          y2="212"
          stroke="#ffffff"
          strokeWidth="1.5"
          strokeDasharray="4 3"
        />
        <text x="58" y="237">
          0 s
        </text>
        <text x="878" y="237" textAnchor="end">
          {((values.length - 1) / fps).toFixed(2)} s
        </text>
        <text x="58" y="14">
          {units}
        </text>
      </svg>
    </div>
  );
}

function EpisodePlayer({
  jobId,
  index,
  episode,
}: {
  jobId: string;
  index: Index;
  episode: Episode;
}) {
  const [signals, setSignals] = useState<Signals | null>(null);
  const [error, setError] = useState("");
  const [frame, setFrame] = useState(0);
  const [displayFrame, setDisplayFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [signal, setSignal] = useState<Signal>("state");
  const videos = useRef<Record<string, HTMLVideoElement | null>>({});
  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/collection/jobs/${jobId}/episodes/${episode.index}/signals`, {
      signal: controller.signal,
    })
      .then(getJSON)
      .then(setSignals)
      .catch((err) => {
        if (!controller.signal.aborted) setError(String(err));
      });
    return () => controller.abort();
  }, [jobId, episode.index]);

  // All media is paused and advances through one common frame clock. A barrier
  // waits for every video to decode the requested frame before advancing the
  // chart or scheduling the next frame. Slow decoding slows playback, not sync.
  useEffect(() => {
    if (!signals) return;
    setReady(false);
    let active = true;
    const pending = new Set(index.cameras);
    const cleanups: (() => void)[] = [];
    for (const view of index.cameras) {
      const video = videos.current[view];
      if (!video) continue;
      const source = episode.videos[view];
      const target = Math.min(
        source.end - 0.5 / index.fps,
        source.start + frame / index.fps,
      );
      const complete = () => {
        if (
          !active ||
          video.seeking ||
          video.readyState < 2 ||
          Math.abs(video.currentTime - target) > 0.001
        )
          return;
        pending.delete(view);
        if (!pending.size) {
          setDisplayFrame(frame);
          setReady(true);
        }
      };
      const position = () => {
        if (!active || video.readyState < 1) return;
        video.pause();
        if (Math.abs(video.currentTime - target) > 0.0001)
          video.currentTime = target;
        complete();
      };
      video.addEventListener("loadedmetadata", position);
      video.addEventListener("loadeddata", position);
      video.addEventListener("seeked", complete);
      video.addEventListener("canplay", complete);
      position();
      cleanups.push(() => {
        video.removeEventListener("loadedmetadata", position);
        video.removeEventListener("loadeddata", position);
        video.removeEventListener("seeked", complete);
        video.removeEventListener("canplay", complete);
      });
    }
    return () => {
      active = false;
      cleanups.forEach((cleanup) => cleanup());
    };
  }, [frame, signals, index, episode]);
  useEffect(() => {
    if (!playing || !ready || error) return;
    if (frame >= episode.frames - 1) {
      setPlaying(false);
      return;
    }
    const timer = window.setTimeout(
      () => setFrame((value) => value + 1),
      1000 / index.fps / speed,
    );
    return () => window.clearTimeout(timer);
  }, [playing, ready, frame, speed, episode.frames, index.fps, error]);
  const seek = (value: number) => {
    setPlaying(false);
    setFrame(Math.max(0, Math.min(episode.frames - 1, value)));
  };
  const units =
    signal === "velocity" ? "rad/s" : signal === "effort" ? "N·m" : "rad";
  if (error)
    return (
      <p role="alert" className="look-error">
        {error}
      </p>
    );
  if (!signals) return <p role="status">Loading episode signals…</p>;
  return (
    <div
      className="dataset-player"
      data-testid="episode-player"
      data-episode={episode.index}
    >
      <div className="dataset-episode-heading">
        <div>
          <small>EPISODE {String(episode.index + 1).padStart(3, "0")}</small>
          <h3>{index.task}</h3>
        </div>
        <span className={`dataset-outcome ${episode.success ? "success" : ""}`}>
          {episode.outcome}
        </span>
      </div>
      {!episode.success && (
        <p className="look-error" role="status">
          {episode.outcome === "timeout"
            ? "This episode reached its time limit before completing the task."
            : "This episode did not complete the task successfully."}{" "}
          Included because failed episodes were enabled during collection.
        </p>
      )}
      <div className="dataset-camera-grid">
        {index.cameras.map((view) => (
          <figure key={view}>
            <figcaption>
              <Camera size={14} />
              {title(view)}
              <span>{index.fps} FPS</span>
            </figcaption>
            <video
              aria-label={`${view} recorded camera`}
              data-view={view}
              data-offset={episode.videos[view].start}
              ref={(element) => {
                videos.current[view] = element;
              }}
              src={episode.videos[view].url}
              muted
              playsInline
              preload="auto"
              onError={() => {
                setPlaying(false);
                setError(`Could not decode the ${view} camera video.`);
              }}
            />
          </figure>
        ))}
      </div>
      <div className="dataset-transport">
        <div className="dataset-transport-row">
          <button
            aria-label="Previous frame"
            disabled={frame === 0}
            onClick={() => seek(frame - 1)}
          >
            <SkipBack size={17} />
          </button>
          <button
            className="dataset-play"
            aria-label={playing ? "Pause episode" : "Play episode"}
            disabled={!ready && !playing}
            onClick={() => {
              if (!playing && frame === episode.frames - 1) setFrame(0);
              setPlaying(!playing);
            }}
          >
            {playing ? <Pause size={16} /> : <Play size={16} />}
            {playing ? "Pause" : "Play"}
          </button>
          <button
            aria-label="Next frame"
            disabled={frame === episode.frames - 1}
            onClick={() => seek(frame + 1)}
          >
            <SkipForward size={17} />
          </button>
          <span data-testid="viewer-frame">
            Frame {displayFrame + 1} / {episode.frames}
          </span>
          <span data-testid="viewer-time">
            {(displayFrame / index.fps).toFixed(3)} s
          </span>
          <label>
            Speed
            <select
              aria-label="Playback speed"
              value={speed}
              onChange={(event) => setSpeed(Number(event.target.value))}
            >
              {[0.25, 0.5, 1, 2].map((value) => (
                <option key={value} value={value}>
                  {value}×
                </option>
              ))}
            </select>
          </label>
        </div>
        <input
          aria-label="Episode frame"
          type="range"
          min={0}
          max={episode.frames - 1}
          step={1}
          value={frame}
          onChange={(event) => seek(Number(event.target.value))}
        />
        <div className="dataset-playback-meta">
          <span data-testid="viewer-ready" role="status">
            {ready ? "All views synchronized" : "Loading synchronized frame…"}
          </span>
          <span>
            Seed {episode.seed} · {(episode.frames / index.fps).toFixed(2)} s ·{" "}
            {index.cameras.length} cameras
          </span>
        </div>
      </div>
      <section className="dataset-trajectory">
        <div className="dataset-section-title">
          <h3>Joint trajectories</h3>
          <select
            aria-label="Trajectory signal"
            value={signal}
            onChange={(event) => setSignal(event.target.value as Signal)}
          >
            <option value="state">Measured position · rad</option>
            <option value="action">Commanded target · rad</option>
            <option value="velocity">Velocity · rad/s</option>
            <option value="effort">Actuator effort · N·m</option>
          </select>
        </div>
        <JointChart
          values={signals[signal]}
          names={index.joint_names}
          frame={displayFrame}
          fps={index.fps}
          units={units}
          seek={seek}
        />
        <div className="dataset-joint-values">
          {index.joint_names.map((name, i) => (
            <div key={name}>
              <span>
                <i style={{ background: colors[i] }} />
                {title(name)}
              </span>
              <b>
                {signals[signal][displayFrame][i].toFixed(4)}{" "}
                <small>{units}</small>
              </b>
            </div>
          ))}
        </div>
        <p className="dataset-tcp">
          Tool position:{" "}
          {signals.tcp[displayFrame].slice(0, 3).map((v, i) => (
            <span key={i}>
              {["X", "Y", "Z"][i]} {v.toFixed(4)} m
            </span>
          ))}
        </p>
      </section>
    </div>
  );
}

export function DatasetViewer({
  jobId,
  back,
}: {
  jobId: string;
  back: () => void;
}) {
  const [index, setIndex] = useState<Index | null>(null);
  const [error, setError] = useState("");
  const [episodeIndex, setEpisodeIndex] = useState(0);
  const [search, setSearch] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/collection/jobs/${jobId}/visualization`, {
      signal: controller.signal,
    })
      .then(getJSON)
      .then((data: Index) => {
        setIndex(data);
        setEpisodeIndex(data.episodes[0]?.index ?? 0);
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(String(err));
      });
    return () => controller.abort();
  }, [jobId]);
  const episode = index?.episodes.find((entry) => entry.index === episodeIndex);
  return (
    <section className="dataset-viewer" aria-label="Dataset visualizer">
      <div className="dataset-viewer-heading">
        <button onClick={back} data-dataset-back>
          <ArrowLeft size={16} />
          Back to datasets
        </button>
        <div>
          <small>DATASET VISUALIZER</small>
          <h2>{index?.name || "Loading dataset…"}</h2>
          <p>{index?.scene_name}</p>
        </div>
        {index && (
          <span>
            {index.episodes.length} episodes ·{" "}
            {index.episodes.filter((entry) => entry.success).length} successful
            ·{" "}
            {index.episodes
              .reduce((sum, entry) => sum + entry.frames, 0)
              .toLocaleString()}{" "}
            frames · {index.cameras.length} views
          </span>
        )}
      </div>
      {error && (
        <p role="alert" className="look-error">
          {error}
        </p>
      )}
      {!index && !error && <p role="status">Reading episode metadata…</p>}
      {index && episode && (
        <div className="dataset-viewer-layout">
          <nav className="dataset-episodes" aria-label="Recorded episodes">
            <label>
              Episodes
              <input
                aria-label="Search episodes"
                placeholder="Episode, seed or outcome…"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </label>
            {index.episodes
              .filter((entry) =>
                `${entry.index + 1} ${entry.seed} ${entry.outcome}`.includes(
                  search.toLowerCase(),
                ),
              )
              .map((entry) => (
                <button
                  key={entry.index}
                  aria-label={`Episode ${entry.index + 1}`}
                  aria-current={
                    entry.index === episodeIndex ? "true" : undefined
                  }
                  onClick={() => setEpisodeIndex(entry.index)}
                >
                  <strong>
                    Episode {String(entry.index + 1).padStart(3, "0")}
                  </strong>
                  <span>
                    {entry.frames} frames · seed {entry.seed}
                  </span>
                  <small className={entry.success ? "success" : ""}>
                    {entry.outcome}
                  </small>
                </button>
              ))}
          </nav>
          <EpisodePlayer
            key={episode.index}
            jobId={jobId}
            index={index}
            episode={episode}
          />
        </div>
      )}
    </section>
  );
}
