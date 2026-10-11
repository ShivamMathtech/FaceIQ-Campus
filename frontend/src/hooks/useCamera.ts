import { useEffect, useRef, useState } from "react";
import { api, Row } from "../services/api";
export function stopTracks(stream: MediaStream | null) {
  stream?.getTracks().forEach((t) => {
    t.onended = null;
    t.stop();
  });
}
export function useCamera(
  sessionId: string,
  interval: number,
  onResult: (data: Row) => void,
) {
  const video = useRef<HTMLVideoElement>(null),
    overlay = useRef<HTMLCanvasElement>(null),
    stream = useRef<MediaStream | null>(null),
    timer = useRef<ReturnType<typeof setTimeout>>(),
    abort = useRef<AbortController | null>(null),
    generation = useRef(0),
    callback = useRef(onResult);
  const [status, setStatus] = useState("OFF"),
    [error, setError] = useState(""),
    [fps, setFps] = useState(0),
    [latency, setLatency] = useState(0),
    [resolution, setResolution] = useState(640);
  callback.current = onResult;
  const stop = () => {
    generation.current++;
    clearTimeout(timer.current);
    abort.current?.abort();
    stopTracks(stream.current);
    stream.current = null;
    if (video.current) video.current.srcObject = null;
    setStatus("OFF");
    setFps(0);
    if (overlay.current)
      overlay.current
        .getContext("2d")
        ?.clearRect(0, 0, overlay.current.width, overlay.current.height);
  };
  useEffect(
    () => () => {
      generation.current++;
      clearTimeout(timer.current);
      abort.current?.abort();
      stopTracks(stream.current);
    },
    [],
  );
  const start = async () => {
    stop();
    setError("");
    setStatus("REQUESTING PERMISSION");
    const current = ++generation.current;
    try {
      if (!navigator.mediaDevices?.getUserMedia)
        throw new Error(
          "Webcam requires localhost or HTTPS in a supported browser.",
        );
      const media = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: resolution },
          height: { ideal: resolution * 0.75 },
          facingMode: "user",
        },
        audio: false,
      });
      if (current !== generation.current) {
        stopTracks(media);
        return;
      }
      stream.current = media;
      media.getVideoTracks().forEach(
        (t) =>
          (t.onended = () => {
            stop();
            setStatus("CAMERA ERROR");
            setError(
              "Camera disconnected. Reconnect it and choose Enable camera.",
            );
          }),
      );
      if (!video.current) {
        stopTracks(media);
        return;
      }
      video.current.srcObject = media;
      await video.current.play();
      setStatus("LIVE");
      const capture = document.createElement("canvas");
      let previous = performance.now();
      const sample = async () => {
        if (current !== generation.current || !video.current) return;
        const begin = performance.now(),
          v = video.current;
        let nextInterval = interval;
        if (!v.videoWidth) {
          timer.current = setTimeout(sample, interval);
          return;
        }
        capture.width = Math.min(resolution, v.videoWidth);
        capture.height = Math.round(
          (v.videoHeight * capture.width) / v.videoWidth,
        );
        capture
          .getContext("2d")!
          .drawImage(v, 0, 0, capture.width, capture.height);
        const blob = await new Promise<Blob | null>((resolve) =>
          capture.toBlob(resolve, "image/jpeg", 0.85),
        );
        if (!blob || current !== generation.current) return;
        const fd = new FormData();
        fd.append("frame", blob, "camera.jpg");
        fd.append("request_id", crypto.randomUUID());
        abort.current = new AbortController();
        try {
          const data = await api(
            "/sessions/" + sessionId + "/recognition-events",
            { method: "POST", body: fd, signal: abort.current.signal },
          );
          if (current !== generation.current) return;
          if (
            data.results.length &&
            data.results.every((r: Row) => r.status === "ALREADY_PRESENT")
          )
            nextInterval = Math.max(interval, 2500);
          callback.current(data);
          setLatency(data.latency_ms);
          setFps(Math.round(10000 / (performance.now() - previous)) / 10);
          previous = performance.now();
          setError("");
          const canvas = overlay.current;
          if (canvas) {
            canvas.width = capture.width;
            canvas.height = capture.height;
            const ctx = canvas.getContext("2d")!;
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.font = "13px system-ui";
            ctx.lineWidth = 2;
            data.results.forEach((r: Row) => {
              if (!r.box) return;
              const [x, y, w, h] = r.box;
              ctx.strokeStyle = [
                "PRESENT_RECORDED",
                "ALREADY_PRESENT",
              ].includes(r.status)
                ? "#41e0bb"
                : "#f8ca75";
              ctx.fillStyle = ctx.strokeStyle;
              ctx.strokeRect(x, y, w, h);
              ctx.fillText(
                (r.name ?? "Face") + " · " + r.status.replaceAll("_", " "),
                Math.max(0, x),
                Math.max(16, y - 8),
              );
            });
          }
        } catch (e) {
          if (current !== generation.current) return;
          const text = e instanceof Error ? e.message : String(e);
          setError(text);
          if (
            /closed|Authentication|expired|setup required|Not authorized|Not assigned/i.test(
              text,
            )
          ) {
            stop();
            setStatus("CAMERA ERROR");
            return;
          }
        }
        if (current === generation.current)
          timer.current = setTimeout(
            sample,
            Math.max(0, nextInterval - (performance.now() - begin)),
          );
      };
      void sample();
    } catch (e) {
      if (current !== generation.current) return;
      stop();
      setStatus("CAMERA ERROR");
      const name = (e as DOMException).name;
      setError(
        name === "NotAllowedError"
          ? "Camera permission was denied. Allow camera access in your browser, then retry."
          : name === "NotFoundError"
            ? "No webcam found. Connect a camera and retry."
            : name === "NotReadableError"
              ? "Camera is busy or unavailable. Close other camera apps and retry."
              : String(e),
      );
    }
  };
  return {
    video,
    overlay,
    status,
    error,
    fps,
    latency,
    start,
    stop,
    resolution,
    setResolution,
  };
}
