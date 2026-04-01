import React, { useState } from "react";
import "./App.css";

function App() {
  const [youtubeLink, setYoutubeLink] = useState("");
  const [responseData, setResponseData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const isValidYouTubeLink = (url) => {
    const pattern =
      /^(https?:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/).+/;
    return pattern.test(url.trim());
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    setError("");
    setResponseData(null);

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
            {loading ? "Processing..." : "Generate Notes"}
          </button>
        </form>

        {error && <p className="error">{error}</p>}

        {responseData && (
          <div className="result">
            <h2>{responseData.message}</h2>

            <p>
              <strong>Video Link:</strong> {responseData.youtube_link}
            </p>

            <p>
              <strong>Video ID:</strong> {responseData.video_id}
            </p>

            <div className="section">
              <h3>Transcript</h3>
              <p>{responseData.transcript}</p>
            </div>

            <div className="section">
              <h3>Important Notes</h3>
              <ul>
                {responseData.notes.map((note, index) => (
                  <li key={index}>{note}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;