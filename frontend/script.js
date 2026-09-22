const targetLanguages = [
    "english", "german", "dutch", "swedish", "danish", "norwegian",
    "spanish", "portuguese", "french", "italian", "romanian",
    "polish", "czech", "slovak", "croatian",
    "finnish", "hungarian", "turkish", "indonesian", "swahili", "vietnamese",
    "russian", "ukrainian", "bulgarian", "serbian"
];

const languageSelect = document.getElementById('languageSelect');
const uploadForm = document.getElementById('uploadForm');
const statusDiv = document.getElementById('status');
const submitBtn = document.getElementById('submitBtn');

// Populate the select dropdown
targetLanguages.forEach(lang => {
    const option = document.createElement('option');
    option.value = lang;
    option.textContent = lang.charAt(0).toUpperCase() + lang.slice(1);
    if (lang === "polish") {
        option.selected = true;
    }
    languageSelect.appendChild(option);
});

// Handle form submission
uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const fileInput = document.getElementById('fileInput');
    if (fileInput.files.length === 0) return;

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('language', languageSelect.value);
    
    statusDiv.textContent = "Uploading document to gateway...";
    statusDiv.className = ""; // Reset styling
    submitBtn.disabled = true;

    try {
        // 1. Initiate asynchronous job via API Gateway
        const response = await fetch('http://localhost:8000/process-pdf', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Server Error (${response.status}): ${errorText}`);
        }

        // 2. Parse the job ID from the JSON response
        const data = await response.json();
        const jobId = data.job_id;
        
        statusDiv.textContent = `Job queued (ID: ${jobId}). Waiting for worker nodes...`;

        // 3. Connect to Event Service to listen for RabbitMQ state changes
        // NOTE: Ensure your SSE Event Service is running on this port and CORS is enabled
        const eventSource = new EventSource(`http://localhost:8000/stream/${jobId}`);

        eventSource.onmessage = (event) => {
            const eventData = JSON.parse(event.data);
            const currentStatus = eventData.status;

            // Format status
            statusDiv.textContent = `Current state: ${currentStatus.replace('_', ' ')}...`;

            // Trigger list refresh on EVERY state change, not just at the end
            fetchAndRenderJobs();

            // Handle pipeline termination states
            if (currentStatus === "COMPLETED") {
                eventSource.close();
                statusDiv.textContent = "Translation complete. Downloading document...";
                statusDiv.className = "success";
                
                const downloadUrl = `http://localhost:9000/translation-jobs/${jobId}/final_translated.pdf`;
                
                const a = document.createElement('a');
                a.href = downloadUrl;
                a.download = `translated_${jobId}.pdf`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                
                submitBtn.disabled = false;
            } else if (currentStatus === "FAILED") {
                eventSource.close();
                throw new Error("Translation pipeline failed during processing.");
            }
        };

        eventSource.onerror = (err) => {
            console.error("SSE Connection Error:", err);
            eventSource.close();
            throw new Error("Lost connection to event stream.");
        };

    } catch (error) {
        statusDiv.textContent = `Error: ${error.message}`;
        statusDiv.className = "error";
        submitBtn.disabled = false;
    }
});

const jobTableBody = document.getElementById('jobTableBody');
const MINIO_BASE_URL = "http://localhost:9000/translation-jobs";

async function fetchAndRenderJobs() {
    try {
        const response = await fetch('http://localhost:8000/jobs');
        const jobs = await response.json();
        
        jobTableBody.innerHTML = '';
        
        jobs.forEach(job => {
            const tr = document.createElement('tr');
            const statusFormatted = job.status.replace('_', ' ');
            const sourceUrl = `${MINIO_BASE_URL}/${job.job_id}/source.pdf`;
            const resultUrl = `${MINIO_BASE_URL}/${job.job_id}/final_translated.pdf`;
            
            const docName = job.filename || "Unknown Document";
            const lang = job.language || "unknown";
            
            const resultLinkHtml = job.status === 'COMPLETED' 
                ? `<a href="${resultUrl}">Result</a>` 
                : `<span class="disabled-link">Result</span>`;

            tr.innerHTML = `
                <td>
                    <div class="doc-name">
                        <strong class="doc-text">${docName}</strong>
                        <span class="tooltiptext">${docName}</span>
                    </div>
                    <span class="lang-label">${lang}</span>
                </td>
                <td>${job.timestamp}</td>
                <td>${statusFormatted}</td>
                <td>
                    <a href="${sourceUrl}" class="source-link" target="_blank">Source</a>
                    ${resultLinkHtml}
                </td>
            `;
            
            jobTableBody.appendChild(tr);
        });
    } catch (error) {
        console.error("Failed to fetch jobs:", error);
    }
}

// Call on page load
fetchAndRenderJobs();
setInterval(fetchAndRenderJobs, 5000);