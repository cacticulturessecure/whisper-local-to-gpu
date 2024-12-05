// staging/js/file-handler.js
class AudioFileHandler {
    constructor() {
        this.fileInput = document.getElementById('audioFile');
        this.uploadButton = document.getElementById('uploadButton');
        this.statusIndicator = document.getElementById('statusIndicator');
        this.resultsBox = document.getElementById('transcriptionResults');
        this.progressSection = document.querySelector('.progress-section');
        this.progressFill = document.querySelector('.progress-fill');
        this.progressText = document.querySelector('.progress-text');
        
        // Configuration
        this.apiEndpoint = '/api/v1/audio/transcribe';
        this.maxFileSize = 50 * 1024 * 1024; // 50MB in bytes
        
        this.setupEventListeners();
        this.checkAPIConnection();
    }

    setupEventListeners() {
        this.fileInput.addEventListener('change', () => this.handleFileSelection());
        this.uploadButton.addEventListener('click', () => this.handleUpload());
        
        // Prevent accidental file drops outside the upload zone
        document.addEventListener('dragover', (e) => e.preventDefault());
        document.addEventListener('drop', (e) => e.preventDefault());
    }

    async checkAPIConnection() {
        try {
            const response = await fetch('/api/v1/health');
            if (response.ok) {
                this.statusIndicator.textContent = 'Ready to process audio files';
                this.fileInput.disabled = false;
            } else {
                throw new Error('API health check failed');
            }
        } catch (error) {
            this.statusIndicator.textContent = 'Error: Cannot connect to transcription service';
            this.fileInput.disabled = true;
            console.error('API Connection Error:', error);
        }
    }

    handleFileSelection() {
        const file = this.fileInput.files[0];
        if (!file) return;

        // Check file type
        if (file.type !== 'audio/wav') {
            this.statusIndicator.textContent = 'Error: Please select a WAV file';
            this.uploadButton.disabled = true;
            return;
        }

        // Check file size
        if (file.size > this.maxFileSize) {
            this.statusIndicator.textContent = 'Error: File size exceeds 50MB limit';
            this.uploadButton.disabled = true;
            return;
        }

        this.uploadButton.disabled = false;
        this.statusIndicator.textContent = `Selected: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)}MB)`;
    }

    updateProgress(percent) {
        this.progressFill.style.width = `${percent}%`;
        this.progressText.textContent = `Uploading: ${Math.round(percent)}%`;
    }

    async handleUpload() {
        const file = this.fileInput.files[0];
        if (!file) return;

        this.progressSection.style.display = 'block';
        this.uploadButton.disabled = true;
        this.fileInput.disabled = true;
        this.statusIndicator.textContent = 'Uploading and processing...';

        const formData = new FormData();
        formData.append('audio', file);

        try {
            const response = await fetch(this.apiEndpoint, {
                method: 'POST',
                body: formData,
                headers: {
                    'Accept': 'application/json',
                },
                onUploadProgress: (progressEvent) => {
                    const percentComplete = (progressEvent.loaded / progressEvent.total) * 100;
                    this.updateProgress(percentComplete);
                }
            });

            if (!response.ok) {
                throw new Error(`Upload failed: ${response.status} ${response.statusText}`);
            }

            const result = await response.json();
            this.displayResults(result);

        } catch (error) {
            console.error('Upload error:', error);
            this.statusIndicator.textContent = `Error: ${error.message}`;
            this.displayResults({
                success: false,
                error: error.message
            });
        } finally {
            this.progressSection.style.display = 'none';
            this.uploadButton.disabled = false;
            this.fileInput.disabled = false;
            this.fileInput.value = '';
        }
    }

    displayResults(result) {
        const timestamp = new Date().toLocaleTimeString();
        
        if (!result.success) {
            this.resultsBox.innerHTML = `
                <div class="transcription-result error">
                    <p><strong>Error at ${timestamp}:</strong></p>
                    <p>${result.error}</p>
                </div>
                ${this.resultsBox.innerHTML}
            `;
            return;
        }

        this.resultsBox.innerHTML = `
            <div class="transcription-result">
                <p><strong>Transcription Result (${timestamp}):</strong></p>
                <p>${result.text}</p>
                <p><strong>Processing Time:</strong> ${result.processing_time}s</p>
                <p><strong>File:</strong> ${this.fileInput.files[0].name}</p>
            </div>
            ${this.resultsBox.innerHTML}
        `;
        this.statusIndicator.textContent = 'Transcription complete';
    }

    // Utility method to format file size
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Error handling utility
    handleError(error, context) {
        console.error(`Error in ${context}:`, error);
        this.statusIndicator.textContent = `Error: ${error.message}`;
        return {
            success: false,
            error: error.message,
            context: context
        };
    }
}

// Initialize the handler when the document loads
document.addEventListener('DOMContentLoaded', () => {
    window.audioHandler = new AudioFileHandler();
});

// Error handling for unexpected issues
window.onerror = function(msg, url, lineNo, columnNo, error) {
    console.error('Global error:', {msg, url, lineNo, columnNo, error});
    const statusIndicator = document.getElementById('statusIndicator');
    if (statusIndicator) {
        statusIndicator.textContent = 'An unexpected error occurred. Please refresh the page.';
    }
    return false;
};
