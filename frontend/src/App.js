import React, { useState } from "react";
import "./App.css";

function App() {
  const [youtubeLink, setYoutubeLink] = useState("");
  const [responseData, setResponseData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [copyMessage, setCopyMessage] = useState("");

  const isValidYouTubeLink = (url) => {
    const pattern =
      /^(https?:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/).+/;
    return pattern.test(url.trim());
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    setError("");
    setResponseData(null);
    setCopyMessage("");

    const cleanLink = youtubeLink.trim();

    if (!cleanLink) {
      setError("Please enter a YouTube link.");
      return;
    }

    if (!isValidYouTubeLink(cleanLink)) {
      setError("Please enter a valid YouTube link.");
      return;
    }

    try {
      setLoading(true);

      const response = await fetch("http://127.0.0.1:5000/api/process", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          youtube_link: cleanLink,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.error || "Something went wrong.");
        return;
      }

      setResponseData(data);
    } catch (err) {
      setError("Cannot connect to backend. Please make sure Flask server is running.");
    } finally {
      setLoading(false);
    }
  };

  const handleCopyTranscript = async () => {
    if (!responseData?.transcript) return;

    try {
      await navigator.clipboard.writeText(responseData.transcript);
      setCopyMessage("Transcript copied successfully.");
      setTimeout(() => setCopyMessage(""), 2000);
    } catch (err) {
      setCopyMessage("Copy failed.");
      setTimeout(() => setCopyMessage(""), 2000);
    }
  };

  const handleDownloadNotes = () => {
    if (!responseData) return;

    const fileContent = `
YouTube Notes Generator

Video Link: ${responseData.youtube_link}
Video ID: ${responseData.video_id}
Audio File: ${responseData.audio_file}

Summary:
${responseData.summary}

Important Notes:
${responseData.important_points.map((point) => `- ${point}`).join("\n")}

Keywords:
${responseData.keywords.join(", ")}

Transcript:
${responseData.transcript}
    `.trim();

    const blob = new Blob([fileContent], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = `video_notes_${responseData.video_id}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="app">
      <div className="card">
        <h1>YouTube Notes Generator</h1>
        <p className="subtitle">
          Paste a YouTube video link and generate notes
        </p>

        <form onSubmit={handleSubmit}>
          <input
            type="text"
            placeholder="Enter YouTube link"
            value={youtubeLink}
            onChange={(e) => setYoutubeLink(e.target.value)}
          />

          <button type="submit" disabled={loading}>
            {loading ? "Processing Video..." : "Generate Notes"}
          </button>
        </form>

        {loading && (
          <div className="loading-box">
            Downloading audio, generating transcript, and preparing notes...
          </div>
        )}

        {error && <p className="error">{error}</p>}

        {responseData && (
          <div className="result">
            <h2>{responseData.message}</h2>

            <div className="info-grid">
              <div className="info-item">
                <span className="label">Video Link</span>
                <span className="value break-text">{responseData.youtube_link}</span>
              </div>

              <div className="info-item">
                <span className="label">Video ID</span>
                <span className="value">{responseData.video_id}</span>
              </div>

              <div className="info-item">
                <span className="label">Audio File</span>
                <span className="value break-text">{responseData.audio_file}</span>
              </div>
            </div>

            <div className="action-buttons">
              <button
                type="button"
                className="secondary-btn"
                onClick={handleDownloadNotes}
              >
                Download Notes
              </button>

              <button
                type="button"
                className="secondary-btn"
                onClick={handleCopyTranscript}
              >
                Copy Transcript
              </button>
            </div>

            {copyMessage && <p className="copy-message">{copyMessage}</p>}

            <div className="section">
              <h3>Summary</h3>
              <div className="section-box">
                <p>{responseData.summary}</p>
              </div>
            </div>

            <div className="section">
              <h3>Important Notes</h3>
              <div className="section-box">
                <ul>
                  {responseData.important_points.map((point, index) => (
                    <li key={index}>{point}</li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="section">
              <h3>Keywords</h3>
              <div className="section-box keywords">
                {responseData.keywords.map((word, index) => (
                  <span className="keyword-tag" key={index}>
                    {word}
                  </span>
                ))}
              </div>
            </div>

            <div className="section">
              <h3>Transcript</h3>
              <div className="section-box transcript-box">
                <p>{responseData.transcript}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;