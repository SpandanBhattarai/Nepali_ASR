
"use client";

import { useRef, useState } from "react";

export default function Home() {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const websocketRef = useRef<WebSocket | null>(null);

  // IMPORTANT: this must be at the component level
  const audioChunksRef = useRef<Blob[]>([]);

  const [recording, setRecording] = useState(false);
  const [status, setStatus] = useState("Ready");
  const [transcription, setTranscription] = useState("");
  const [audioChunks, setAudioChunks] = useState(0);
  const [messages, setMessages] = useState<string[]>([]);

  const startRecording = async () => {
    try {
      setMessages([]);
      setAudioChunks(0);
      audioChunksRef.current = [];

      // Connect to FastAPI
      const websocket = new WebSocket("ws://localhost:8000/ws");

      websocket.onopen = () => {
        console.log("WebSocket connected");
        setStatus("Connected to ASR backend");
      };

     websocket.onmessage = (event) => {
  console.log("Backend response:", event.data);

  try {
    const data = JSON.parse(event.data);

    console.log("Parsed response:", data);

    if (data.status === "success") {
      setTranscription(data.text);
      setStatus("Transcription complete");
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
        setStatus("Disconnected from ASR backend");
      };

      websocketRef.current = websocket;

      // Get microphone
      const stream =
        await navigator.mediaDevices.getUserMedia({
          audio: true,
        });

      // Check supported recording format
      let mimeType = "";

      if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
        mimeType = "audio/webm;codecs=opus";
      } else if (MediaRecorder.isTypeSupported("audio/webm")) {
        mimeType = "audio/webm";
      } else {
        mimeType = "";
      }

      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      recorder.onstart = () => {
        console.log("Recording started");

        setRecording(true);
        setStatus("Listening...");
      };

      // Collect chunks.
      // DO NOT send them individually.
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);

          setAudioChunks(
            audioChunksRef.current.length
          );

          console.log(
            "Collected audio chunk:",
            event.data.size,
            "bytes"
          );
        }
      };

      recorder.onstop = async () => {
        console.log("Recording stopped");

        stream.getTracks().forEach((track) => {
          track.stop();
        });

        setRecording(false);
        setStatus("Processing audio...");

        if (audioChunksRef.current.length === 0) {
          setStatus("No audio recorded");
          return;
        }

        // Combine all chunks into ONE complete WebM file
        const audioBlob = new Blob(
          audioChunksRef.current,
          {
            type: recorder.mimeType || "audio/webm",
          }
        );

        console.log(
          "Complete recording:",
          audioBlob.size,
          "bytes"
        );

        // Clear chunks for the next recording
        audioChunksRef.current = [];

        // Send the complete recording to FastAPI
        if (
          websocket.readyState ===
          WebSocket.OPEN
        ) {
          const buffer =
            await audioBlob.arrayBuffer();

          console.log(
            "Sending complete recording:",
            buffer.byteLength,
            "bytes"
          );

          websocket.send(buffer);

          setStatus(
            "Audio sent to ASR backend"
          );
        } else {
          setStatus(
            "Backend connection closed"
          );
        }
      };

      mediaRecorderRef.current = recorder;

      // Start recording.
      // We intentionally do NOT use start(1000).
      recorder.start();

    } catch (error) {
      console.error(
        "Microphone error:",
        error
      );

      setStatus(
        "Could not access microphone"
      );
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
          Nepali Live ASR
        </h1>

        <p className="mt-2 text-center text-gray-600">
          IndicConformer
        </p>

        <div className="mt-10 flex justify-center">
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
        </div>

        <div className="mt-8 rounded-lg bg-gray-50 p-4 text-center">

          <p className="font-semibold text-gray-900">
            Status
          </p>

          <p className="mt-1 text-gray-700">
            {recording && "🔴 "}
            {status}
          </p>

          <p className="mt-2 text-sm text-gray-500">
            Audio chunks collected:{" "}
            {audioChunks}
          </p>

        </div>

        <div className="mt-8">

          <h2 className="text-xl font-semibold text-gray-900">
            Backend Messages
          </h2>

          <div className="mt-3 min-h-32 rounded-lg border bg-gray-50 p-4 text-gray-900">

            {messages.length === 0 ? (
              <p className="text-gray-400">
                Waiting for backend...
              </p>
            ) : (
              messages.map(
                (message, index) => (
                  <p key={index}>
                    {message}
                  </p>
                )
              )
            )}

          </div>

        </div>

        <div className="mt-8">

          <h2 className="text-xl font-semibold text-gray-900">
            Transcription
          </h2>

          <div className="mt-3 min-h-32 rounded-lg border bg-gray-50 p-4 text-lg text-gray-900">
            {transcription || "Your Nepali transcription will appear here..."}
          </div>

        </div>

      </div>
    </main>
  );
}
