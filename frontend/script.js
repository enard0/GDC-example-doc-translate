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
const jobTableBody = document.getElementById('jobTableBody');
const MINIO_BASE_URL = "http://localhost:9000/translation-jobs";

let activeJobId = null; // Tracks the job submitted from this specific tab

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
    statusDiv.className = "";
    submitBtn.disabled = true;

    try {
        const response = await fetch('http://localhost:8000/process-pdf', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Server Error (${response.status}): ${errorText}`);
        }

        const data = await response.json();
        activeJobId = data.job_id; // Set the tracker
        
        statusDiv.textContent = `Job queued. Waiting for worker nodes...`;
        
        // Force an immediate table refresh so the pending job appears instantly
        fetchAndRenderJobs(); 

    } catch (error) {
        statusDiv.textContent = `Error: ${error.message}`;
        statusDiv.className = "error";
        submitBtn.disabled = false;
    }
});

// Fetch and render table, and handle active job state
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

            // Handle UI updates and auto-download for the active job
            if (job.job_id === activeJobId) {
                if (job.status === 'COMPLETED') {
                    statusDiv.textContent = "Translation complete. Downloading document...";
                    statusDiv.className = "success";
                    submitBtn.disabled = false;
                    activeJobId = null; // Clear tracker to prevent duplicate downloads
                    
                    const a = document.createElement('a');
                    a.href = resultUrl;
                    a.setAttribute('download', ''); // The backend Content-Disposition header dictates the filename
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    
                } else if (job.status === 'FAILED') {
                    statusDiv.textContent = "Error: Translation pipeline failed.";
                    statusDiv.className = "error";
                    submitBtn.disabled = false;
                    activeJobId = null;
                } else {
                    statusDiv.textContent = `Current state: ${statusFormatted}...`;
                }
            }
        });
    } catch (error) {
        console.error("Failed to fetch jobs:", error);
    }
}

// Initial load and polling setup
fetchAndRenderJobs();
setInterval(fetchAndRenderJobs, 5000);