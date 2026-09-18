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
    statusDiv.textContent = "Processing document. This may take several minutes...";
    submitBtn.disabled = true;

    try {
        // Point this to your backend gateway address
        const response = await fetch('http://localhost:8000/process-pdf', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Server Error (${response.status}): ${errorText}`);
        }

        // Handle the incoming PDF binary
        const blob = await response.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = `translated_document_${languageSelect.value}.pdf`;
        document.body.appendChild(a);
        a.click();
        
        document.body.removeChild(a);
        window.URL.revokeObjectURL(downloadUrl);

        statusDiv.textContent = "Translation complete. Download started.";
    } catch (error) {
        statusDiv.textContent = `Error: ${error.message}`;
    } finally {
        submitBtn.disabled = false;
    }
});