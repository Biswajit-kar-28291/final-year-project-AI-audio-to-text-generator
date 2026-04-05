import React, { useState } from "react";
import "./App.css";
import jsPDF from "jspdf";

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

  const handleDownloadTXT = () => {
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

  const addWrappedText = (doc, text, x, y, maxWidth, lineHeight) => {
    const lines = doc.splitTextToSize(text, maxWidth);
    doc.text(lines, x, y);
    return y + lines.length * lineHeight;
  };

  const handleDownloadPDF = () => {
    if (!responseData) return;

    const doc = new jsPDF();
    const pageWidth = doc.internal.pageSize.getWidth();
    const pageHeight = doc.internal.pageSize.getHeight();
    const margin = 15;
    const maxWidth = pageWidth - margin * 2;
    const lineHeight = 7;
    let y = 20;

    const checkPageBreak = (neededHeight = 10) => {
      if (y + neededHeight > pageHeight - 15) {
        doc.addPage();
        y = 20;
      }
    };

    doc.setFont("helvetica", "bold");
    doc.setFontSize(18);
    doc.text("YouTube Notes Generator", margin, y);
    y += 12;

    doc.setFontSize(11);
    doc.setFont("helvetica", "normal");

    checkPageBreak();
    y = addWrappedText(doc, `Video Link: ${responseData.youtube_link}`, margin, y, maxWidth, lineHeight);
    y += 2;

    checkPageBreak();
    y = addWrappedText(doc, `Video ID: ${responseData.video_id}`, margin, y, maxWidth, lineHeight);
    y += 2;

    checkPageBreak();
    y = addWrappedText(doc, `Audio File: ${responseData.audio_file}`, margin, y, maxWidth, lineHeight);
    y += 8;

    checkPageBreak();
    doc.setFont("helvetica", "bold");
    doc.text("Summary", margin, y);
    y += 8;

    doc.setFont("helvetica", "normal");
    y = addWrappedText(doc, responseData.summary || "No summary available.", margin, y, maxWidth, lineHeight);
    y += 8;

    checkPageBreak();
    doc.setFont("helvetica", "bold");
    doc.text("Important Notes", margin, y);
    y += 8;

    doc.setFont("helvetica", "normal");
    if (responseData.important_points?.length) {
      responseData.important_points.forEach((point) => {
        checkPageBreak(20);
        y = addWrappedText(doc, `• ${point}`, margin, y, maxWidth, lineHeight);
        y += 2;
      });
    } else {
      y = addWrappedText(doc, "No important notes available.", margin, y, maxWidth, lineHeight);
      y += 4;
    }

    y += 6;
    checkPageBreak();

    doc.setFont("helvetica", "bold");
    doc.text("Keywords", margin, y);
    y += 8;

    doc.setFont("helvetica", "normal");
    y = addWrappedText(
      doc,
      responseData.keywords?.length
        ? responseData.keywords.join(", ")
        : "No keywords available.",
      margin,
      y,
      maxWidth,
      lineHeight
    );

    y += 8;
    checkPageBreak();

    doc.setFont("helvetica", "bold");
    doc.text("Transcript", margin, y);
    y += 8;

    doc.setFont("helvetica", "normal");
    const transcriptLines = doc.splitTextToSize(
      responseData.transcript || "No transcript available.",
      maxWidth
    );

    transcriptLines.forEach((line) => {
      checkPageBreak(10);
      doc.text(line, margin, y);
      y += lineHeight;
    });

    doc.save(`video_notes_${responseData.video_id}.pdf`);
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
                onClick={handleDownloadTXT}
              >
                Download Notes TXT
              </button>

              <button
                type="button"
                className="secondary-btn"
                onClick={handleDownloadPDF}
              >
                Download Notes PDF
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