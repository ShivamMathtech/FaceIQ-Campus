import { describe, it, expect, vi, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { stopTracks, useCamera } from "./useCamera";
afterEach(() => vi.restoreAllMocks());
describe("camera resource lifecycle", () => {
  it("releases every track", () => {
    const a = { stop: vi.fn(), onended: vi.fn() },
      b = { stop: vi.fn(), onended: vi.fn() };
    stopTracks({ getTracks: () => [a, b] } as unknown as MediaStream);
    expect(a.stop).toHaveBeenCalledOnce();
    expect(b.stop).toHaveBeenCalledOnce();
    expect(a.onended).toBeNull();
  });
  it("shows permission denial and leaves camera stopped", async () => {
    Object.defineProperty(navigator, "mediaDevices", {
      value: {
        getUserMedia: vi
          .fn()
          .mockRejectedValue(new DOMException("Denied", "NotAllowedError")),
      },
      configurable: true,
    });
    const { result } = renderHook(() => useCamera("session", 800, vi.fn()));
    await act(async () => {
      await result.current.start();
    });
    expect(result.current.status).toBe("CAMERA ERROR");
    expect(result.current.error).toMatch(/permission was denied/);
  });
  it("releases a delayed permission stream after unmount", async () => {
    let resolve!: (s: MediaStream) => void;
    const pending = new Promise<MediaStream>((r) => (resolve = r));
    Object.defineProperty(navigator, "mediaDevices", {
      value: { getUserMedia: vi.fn().mockReturnValue(pending) },
      configurable: true,
    });
    const track = { stop: vi.fn(), onended: null };
    const stream = { getTracks: () => [track] } as unknown as MediaStream;
    const { result, unmount } = renderHook(() =>
      useCamera("session", 800, vi.fn()),
    );
    let start: Promise<void>;
    act(() => {
      start = result.current.start();
    });
    unmount();
    await act(async () => {
      resolve(stream);
      await start;
    });
    expect(track.stop).toHaveBeenCalledOnce();
  });
});
