"use client";

import { useEffect, useRef, useState } from "react";

const MIN_NUMBER = 1;
const MAX_NUMBER = 9999;

const DEVANAGARI_DIGITS = ["०", "१", "२", "३", "४", "५", "६", "७", "८", "९"];

const toDevanagari = (n: number) =>
  String(n)
    .split("")
    .map((d) => DEVANAGARI_DIGITS[Number(d)])
    .join("");

const randomNumber = () =>
  Math.floor(Math.random() * (MAX_NUMBER - MIN_NUMBER + 1)) + MIN_NUMBER;

export default function Home() {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const websocketRef = useRef<WebSocket | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const [recording, setRecording] = useState(false);
  const [status, setStatus] = useState("Ready");
  const [transcription, setTranscription] = useState("");
  const [targetNumber, setTargetNumber] = useState<number | null>(null);

  // Generate the number on the client only (avoids SSR hydration mismatch)
  useEffect(() => {
    setTargetNumber(randomNumber());
  }, []);

  // Close the socket if the component unmounts
  useEffect(() => {
    return () => {
      websocketRef.current?.close();
    };
  }, []);

  const newNumber = () => {
    if (recording) return;
    setTargetNumber(randomNumber());
    setTranscription("");
    setStatus("Ready");
  };

  const startRecording = async () => {
    try {
      setTranscription("");
      audioChunksRef.current = [];

      // Close any previous connection
      if (websocketRef.current) {
        websocketRef.current.close();
      }

      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      const websocket = new WebSocket(`${protocol}://${window.location.host}/ws`);

      websocket.onopen = () => {
        console.log("WebSocket connected");
        setStatus("Connected to ASR backend");
      };

      websocket.onmessage = (event) => {
        console.log("Backend response:", event.data);

        try {
          const data = JSON.parse(event.data);

          const text = typeof data.text === "string" ? data.text.trim() : "";

          if (data.status === "success" && text) {
            setTranscription(text);
            setStatus("Transcription complete");
          } else if (data.status === "success") {
            setStatus("No speech recognized");
          } else {
            setStatus(data.message || "Transcription failed");
          }
        } catch (error) {
          console.error("Could not parse backend response:", error);
          setStatus("Invalid response from backend");
        }
      };

      websocket.onerror = (error) => {
        console.error("WebSocket error:", error);
        setStatus("WebSocket error");
      };

      websocket.onclose = () => {
        console.log("WebSocket disconnected");
      };

      websocketRef.current = websocket;

      // Get microphone
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      let mimeType = "";
      if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
        mimeType = "audio/webm;codecs=opus";
      } else if (MediaRecorder.isTypeSupported("audio/webm")) {
        mimeType = "audio/webm";
      }

      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      recorder.onstart = () => {
        setRecording(true);
        setStatus("Listening...");
      };

      // Collect chunks; send them together as one file when stopped
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());

        setRecording(false);
        setStatus("Processing audio...");

        if (audioChunksRef.current.length === 0) {
          setStatus("No audio recorded");
          return;
        }

        const audioBlob = new Blob(audioChunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });

        audioChunksRef.current = [];

        // The socket may still be connecting if the recording was very short
        if (websocket.readyState === WebSocket.CONNECTING) {
          await new Promise<void>((resolve) => {
            websocket.addEventListener("open", () => resolve(), { once: true });
            websocket.addEventListener("error", () => resolve(), { once: true });
          });
        }

        if (websocket.readyState === WebSocket.OPEN) {
          const buffer = await audioBlob.arrayBuffer();
          websocket.send(buffer);
          setStatus("Transcribing...");
        } else {
          setStatus("Backend connection closed");
        }
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
    } catch (error) {
      console.error("Microphone error:", error);
      setStatus("Could not access microphone");
    }
  };

  const stopRecording = () => {
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state !== "inactive"
    ) {
      mediaRecorderRef.current.stop();
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-100 p-6 text-gray-900">
      <div className="w-full max-w-2xl rounded-2xl bg-white p-8 shadow-lg">
        <h1 className="text-3xl font-bold text-center text-gray-900">
          Nepali Number ASR
        </h1>

        <p className="mt-2 text-center text-gray-600">
          Say the number below in Nepali or English
        </p>

        {/* Number prompt */}
        <div className="mt-10 flex flex-col items-center justify-center rounded-2xl bg-blue-50 py-12">
          <span className="text-9xl font-extrabold text-blue-700 leading-none">
            {targetNumber ?? "–"}
          </span>
          {targetNumber !== null && (
            <span className="mt-4 text-3xl text-blue-400">
              {toDevanagari(targetNumber)}
            </span>
          )}
        </div>

        {/* Controls */}
        <div className="mt-8 flex items-center justify-center gap-4">
          {!recording ? (
            <button
              onClick={startRecording}
              className="rounded-full bg-blue-600 px-8 py-4 text-lg font-semibold text-white hover:bg-blue-700"
            >
              🎤 Start Recording
            </button>
          ) : (
            <button
              onClick={stopRecording}
              className="rounded-full bg-red-600 px-8 py-4 text-lg font-semibold text-white hover:bg-red-700"
            >
              ⏹ Stop Recording
            </button>
          )}

          <button
            onClick={newNumber}
            disabled={recording}
            className="rounded-full bg-gray-200 px-6 py-4 text-lg font-semibold text-gray-800 hover:bg-gray-300 disabled:cursor-not-allowed disabled:opacity-50"
          >
            🔄 New Number
          </button>
        </div>

        {/* Status */}
        <div className="mt-8 rounded-lg bg-gray-50 p-4 text-center">
          <p className="font-semibold text-gray-900">Status</p>
          <p className="mt-1 text-gray-700">
            {recording && "🔴 "}
            {status}
          </p>
        </div>

        {/* Transcription */}
        <div className="mt-8">
          <h2 className="text-xl font-semibold text-gray-900">You said</h2>

          <div className="mt-3 min-h-32 rounded-lg border bg-gray-50 p-4 text-2xl text-gray-900">
            {transcription || "Your Nepali transcription will appear here..."}
          </div>
        </div>
      </div>
    </main>
  );
}